(() => {
  const SESSION_ID = window.DEBATE_SESSION_ID;
  const STATUS_LABELS = window.DEBATE_STATUS_LABELS || {};
  const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];

  const cards = Array.from(document.querySelectorAll(".part-card"));
  const staleBanner = document.getElementById("stale-recording-banner");
  const allDoneSection = document.getElementById("all-done-section");
  const overallLabel = document.getElementById("overall-progress-label");

  /** @type {string|null} 同時に1パートしか録音できないようにするロック */
  let activeRecordingPart = null;

  const cardState = new Map();

  // ── 時間経過の合図音（残り1分:1回／残り30秒:2回／制限到達後:連打） ──────
  let audioCtx = null;
  function getAudioCtx() {
    if (!audioCtx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return null;
      audioCtx = new AudioCtx();
    }
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
  }

  function playBeep(delaySec = 0, freq = 880, duration = 0.14, volume = 0.35) {
    const ctx = getAudioCtx();
    if (!ctx) return;
    const startTime = ctx.currentTime + delaySec;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, startTime);
    gain.gain.exponentialRampToValueAtTime(volume, startTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
    osc.connect(gain).connect(ctx.destination);
    osc.start(startTime);
    osc.stop(startTime + duration + 0.02);
  }

  function playBeepSequence(count, interval = 0.22) {
    for (let i = 0; i < count; i += 1) {
      playBeep(i * interval);
    }
  }

  function pickMimeType() {
    if (!window.MediaRecorder) return "";
    for (const type of MIME_CANDIDATES) {
      if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return "";
  }

  function extensionFor(mimeType) {
    if (mimeType.includes("mp4")) return "mp4";
    if (mimeType.includes("ogg")) return "ogg";
    return "webm";
  }

  function formatSeconds(totalSeconds) {
    const sec = Math.max(0, Math.floor(totalSeconds || 0));
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function setError(card, message) {
    const el = card.querySelector(".part-error");
    if (!message) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = message;
    el.classList.remove("hidden");
  }

  function refreshOverallProgress() {
    const total = cards.length;
    const confirmed = cards.filter((c) => c.dataset.status === "confirmed").length;
    overallLabel.textContent = `${confirmed}/${total} パート確定`;

    document.querySelectorAll("[data-step-part]").forEach((dot) => {
      const card = cards.find((c) => c.dataset.part === dot.dataset.stepPart);
      const status = card ? card.dataset.status : "not_started";
      const colorByStatus = {
        not_started: "bg-slate-200",
        recording: "bg-rose-400",
        transcribing: "bg-amber-400",
        needs_review: "bg-sky-400",
        confirmed: "bg-emerald-500",
      };
      dot.className = `h-1.5 rounded-full step-dot ${colorByStatus[status] || "bg-slate-200"}`;
    });

    allDoneSection.classList.toggle("hidden", confirmed !== total);
  }

  function setRecordButtonsDisabled(exceptPart, disabled) {
    cards.forEach((card) => {
      if (card.dataset.part === exceptPart) return;
      const btn = card.querySelector(".btn-record");
      btn.disabled = disabled;
      btn.classList.toggle("opacity-40", disabled);
      btn.classList.toggle("cursor-not-allowed", disabled);
    });
  }

  function renderCard(card) {
    const status = card.dataset.status;
    const part = card.dataset.part;
    const timeLimit = Number(card.dataset.timeLimit || 0);
    const elapsed = card.dataset.elapsed ? Number(card.dataset.elapsed) : null;

    const recordBtn = card.querySelector(".btn-record");
    const stopBtn = card.querySelector(".btn-stop");
    const reviewBtn = card.querySelector(".btn-review");
    const resetBtn = card.querySelector(".btn-reset");
    const uploadingLabel = card.querySelector(".btn-uploading");
    const pill = card.querySelector("[data-status-pill]");
    const timerEl = card.querySelector("[data-timer]");

    pill.textContent = STATUS_LABELS[status] || status;
    pill.className = `status-pill status-${status}`;

    recordBtn.classList.add("hidden");
    stopBtn.classList.add("hidden");
    reviewBtn.classList.add("hidden");
    resetBtn.classList.add("hidden");
    uploadingLabel.classList.add("hidden");

    const state = cardState.get(part) || {};

    if (status === "not_started") {
      recordBtn.classList.remove("hidden");
      timerEl.textContent = formatSeconds(0);
      timerEl.classList.remove("text-rose-600");
    } else if (status === "recording") {
      stopBtn.classList.remove("hidden");
    } else if (status === "transcribing") {
      uploadingLabel.classList.remove("hidden");
    } else if (status === "needs_review") {
      reviewBtn.classList.remove("hidden");
      resetBtn.classList.remove("hidden");
      reviewBtn.textContent = "文字起こしを確認";
      if (elapsed !== null) {
        timerEl.textContent = formatSeconds(elapsed);
        timerEl.classList.toggle("text-rose-600", elapsed > timeLimit);
      }
    } else if (status === "confirmed") {
      reviewBtn.classList.remove("hidden");
      resetBtn.classList.remove("hidden");
      reviewBtn.textContent = "文字起こしを見る";
      if (elapsed !== null) {
        timerEl.textContent = formatSeconds(elapsed);
        timerEl.classList.toggle("text-rose-600", elapsed > timeLimit);
      }
    }

    cardState.set(part, state);
    refreshOverallProgress();
  }

  function startClientTimer(card) {
    const part = card.dataset.part;
    const timeLimit = Number(card.dataset.timeLimit || 0);
    const timerEl = card.querySelector("[data-timer]");
    const startedAt = Date.now();

    const state = cardState.get(part) || {};
    state.cuesFired = { oneMin: false, thirtySec: false };
    state.alarmIntervalId = null;
    cardState.set(part, state);

    const intervalId = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      const remaining = timeLimit - elapsed;
      timerEl.textContent = formatSeconds(elapsed);
      timerEl.classList.toggle("text-rose-600", remaining < 0);

      const s = cardState.get(part) || {};
      if (!s.cuesFired.oneMin && remaining <= 60 && remaining > 30) {
        s.cuesFired.oneMin = true;
        playBeepSequence(1);
      }
      if (!s.cuesFired.thirtySec && remaining <= 30 && remaining > 0) {
        s.cuesFired.thirtySec = true;
        playBeepSequence(2);
      }
      if (remaining <= 0 && !s.alarmIntervalId) {
        playBeepSequence(2);
        s.alarmIntervalId = setInterval(() => playBeepSequence(2), 1000);
      }
      cardState.set(part, s);
    }, 500);

    state.intervalId = intervalId;
    cardState.set(part, state);
  }

  function stopClientTimer(part) {
    const state = cardState.get(part) || {};
    if (state.intervalId) {
      clearInterval(state.intervalId);
      state.intervalId = null;
    }
    if (state.alarmIntervalId) {
      clearInterval(state.alarmIntervalId);
      state.alarmIntervalId = null;
    }
    cardState.set(part, state);
  }

  async function handleRecordClick(card) {
    const part = card.dataset.part;
    if (activeRecordingPart) return;
    setError(card, "");

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError(card, "このブラウザはマイク録音に対応していません。");
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      setError(card, "マイクへのアクセスが許可されませんでした。");
      return;
    }

    try {
      const res = await fetch(`/debate/api/sessions/${SESSION_ID}/parts/${part}/start`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("録音開始の記録に失敗しました。");
    } catch (err) {
      setError(card, err.message);
      stream.getTracks().forEach((t) => t.stop());
      return;
    }

    const mimeType = pickMimeType();
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);
    const chunks = [];

    recorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    });

    recorder.addEventListener("stop", () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
      uploadAudio(card, blob, mimeType || "audio/webm");
    });

    activeRecordingPart = part;
    setRecordButtonsDisabled(part, true);

    const state = cardState.get(part) || {};
    state.recorder = recorder;
    cardState.set(part, state);

    card.dataset.status = "recording";
    renderCard(card);
    startClientTimer(card);

    recorder.start();
  }

  function handleStopClick(card) {
    const part = card.dataset.part;
    const state = cardState.get(part) || {};
    if (!state.recorder || state.recorder.state === "inactive") return;

    stopClientTimer(part);
    card.dataset.status = "transcribing";
    renderCard(card);
    state.recorder.stop();
  }

  async function uploadAudio(card, blob, mimeType) {
    const part = card.dataset.part;
    const formData = new FormData();
    formData.append("audio", blob, `${part}.${extensionFor(mimeType)}`);

    try {
      const res = await fetch(`/debate/api/sessions/${SESSION_ID}/parts/${part}/audio`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      activeRecordingPart = null;
      setRecordButtonsDisabled(part, false);

      const partData = data.part || data;
      card.dataset.status = partData.status || "needs_review";
      card.dataset.elapsed = partData.elapsed_sec ?? "";
      renderCard(card);

      if (!res.ok) {
        setError(card, data.error || "文字起こしに失敗しました。文字起こし確認画面から手動で入力できます。");
        return;
      }

      window.location.href = `/debate/session/${SESSION_ID}/parts/${part}/review`;
    } catch (err) {
      activeRecordingPart = null;
      setRecordButtonsDisabled(part, false);
      card.dataset.status = "needs_review";
      renderCard(card);
      setError(card, "アップロードに失敗しました。ネットワークをご確認のうえ、やり直してください。");
    }
  }

  async function handleResetClick(card) {
    const part = card.dataset.part;
    if (!window.confirm(`${part} パートの録音・文字起こしをリセットしてやり直しますか？`)) return;

    try {
      const res = await fetch(`/debate/api/sessions/${SESSION_ID}/parts/${part}/reset`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "リセットに失敗しました。");

      card.dataset.status = data.status;
      card.dataset.elapsed = "";
      setError(card, "");
      renderCard(card);
    } catch (err) {
      setError(card, err.message);
    }
  }

  function handleReviewClick(card) {
    const part = card.dataset.part;
    window.location.href = `/debate/session/${SESSION_ID}/parts/${part}/review`;
  }

  async function resetStaleRecording(card) {
    const part = card.dataset.part;
    try {
      const res = await fetch(`/debate/api/sessions/${SESSION_ID}/parts/${part}/reset`, {
        method: "POST",
      });
      const data = await res.json();
      if (res.ok) {
        card.dataset.status = data.status;
        card.dataset.elapsed = "";
        renderCard(card);
        staleBanner.classList.remove("hidden");
      }
    } catch (err) {
      // 通信できなくても致命的ではないため無視する
    }
  }

  cards.forEach((card) => {
    card.querySelector(".btn-record").addEventListener("click", () => handleRecordClick(card));
    card.querySelector(".btn-stop").addEventListener("click", () => handleStopClick(card));
    card.querySelector(".btn-reset").addEventListener("click", () => handleResetClick(card));
    card.querySelector(".btn-review").addEventListener("click", () => handleReviewClick(card));

    if (card.dataset.status === "recording") {
      // ページ再読み込みでMediaRecorderの実体は失われているため、サーバー側もリセットする
      resetStaleRecording(card);
    } else {
      renderCard(card);
    }
  });

  refreshOverallProgress();
})();
