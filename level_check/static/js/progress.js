(() => {
  const SESSION_ID = window.LEVEL_CHECK_SESSION_ID;
  const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  const VAD_THRESHOLD = 0.06; // RMS しきい値（マイク入力レベルに合わせた簡易 Voice Activity Detection）
  const STATUS_LABELS = {
    not_started: "未実施",
    recording: "録音中",
    transcribing: "文字起こし中",
    scoring: "採点中",
    done: "完了",
    error: "エラー",
  };

  const cards = Array.from(document.querySelectorAll(".part-card"));
  const allDoneSection = document.getElementById("all-done-section");
  const overallLabel = document.getElementById("overall-progress-label");
  const micErrorBanner = document.getElementById("mic-error-banner");

  let activeRecordingPart = null;
  const cardState = new Map();

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

  function updateRecordButtonStates() {
    cards.forEach((card) => {
      const btn = card.querySelector(".btn-record");
      if (!btn || card.dataset.status !== "not_started") return;
      const locked = activeRecordingPart !== null;
      btn.disabled = locked;
      btn.classList.toggle("opacity-40", locked);
      btn.classList.toggle("cursor-not-allowed", locked);
    });
  }

  function refreshOverallProgress() {
    const total = cards.length;
    const finished = cards.filter((c) => ["done", "error"].includes(c.dataset.status)).length;
    overallLabel.textContent = `${finished}/${total} 問完了`;

    document.querySelectorAll("[data-step-part]").forEach((dot) => {
      const card = cards.find((c) => c.dataset.partId === dot.dataset.stepPart);
      const status = card ? card.dataset.status : "not_started";
      const colorByStatus = {
        not_started: "bg-slate-200",
        recording: "bg-rose-400",
        transcribing: "bg-amber-400",
        scoring: "bg-amber-400",
        done: "bg-emerald-500",
        error: "bg-rose-500",
      };
      dot.className = `h-1.5 rounded-full step-dot ${colorByStatus[status] || "bg-slate-200"}`;
    });

    allDoneSection.classList.toggle("hidden", finished !== total);
    updateRecordButtonStates();
  }

  function renderCard(card) {
    const status = card.dataset.status;
    const recordBtn = card.querySelector(".btn-record");
    const stopBtn = card.querySelector(".btn-stop");
    const retryBtn = card.querySelector(".btn-retry");
    const processingLabel = card.querySelector(".btn-processing");
    const pill = card.querySelector("[data-status-pill]");

    pill.textContent = STATUS_LABELS[status] || status;
    pill.className = `status-pill status-${status}`;

    recordBtn.classList.add("hidden");
    stopBtn.classList.add("hidden");
    retryBtn.classList.add("hidden");
    processingLabel.classList.add("hidden");

    if (status === "not_started") {
      recordBtn.classList.remove("hidden");
    } else if (status === "recording") {
      stopBtn.classList.remove("hidden");
    } else if (status === "transcribing" || status === "scoring") {
      processingLabel.classList.remove("hidden");
    } else if (status === "done") {
      retryBtn.classList.remove("hidden");
    } else if (status === "error") {
      retryBtn.classList.remove("hidden");
    }

    refreshOverallProgress();
  }

  // ── 出題提示（リピート課題=音声、文再構成=単語チップ、Q&A=文章） ──
  function speak(text, onEnd) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      onEnd();
      return false;
    }
    try {
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = "en-US";
      utter.rate = 0.95;
      utter.onend = onEnd;
      utter.onerror = onEnd;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utter);
      return true;
    } catch (_) {
      onEnd();
      return false;
    }
  }

  function setupStimulus(card) {
    const taskType = card.dataset.taskType;
    const state = cardState.get(card.dataset.partId) || {};

    if (taskType === "repeat") {
      const targetText = card.dataset.targetText || "";
      const textEl = card.querySelector("[data-repeat-text]");
      const noteEl = card.querySelector("[data-repeat-hidden-note]");
      const recordBtn = card.querySelector(".btn-record");
      const replayBtn = card.querySelector(".btn-replay");

      const playStimulus = () => {
        if (recordBtn) {
          recordBtn.disabled = true;
          recordBtn.textContent = "🔊 再生中...";
        }
        const spoke = speak(targetText, () => {
          state.stimulusReadyAt = Date.now();
          cardState.set(card.dataset.partId, state);
          if (recordBtn && card.dataset.status === "not_started") {
            recordBtn.disabled = false;
            recordBtn.textContent = "● 録音開始";
          }
        });
        if (!spoke) {
          // 音声合成非対応ブラウザ: フォールバックとして文章を表示する
          if (textEl) textEl.classList.remove("hidden");
          if (noteEl) noteEl.textContent = "🔊 音声再生に対応していないため、文章を表示しました。読んでそのまま復唱してください。";
          state.stimulusReadyAt = Date.now();
          cardState.set(card.dataset.partId, state);
        }
      };

      replayBtn?.addEventListener("click", playStimulus);
      playStimulus();
    } else if (taskType === "sentence_build") {
      const words = JSON.parse(card.dataset.shuffledWords || "[]");
      const container = card.querySelector("[data-word-chips]");
      if (container) {
        container.innerHTML = "";
        words.forEach((w) => {
          const chip = document.createElement("span");
          chip.className = "word-chip";
          chip.textContent = w;
          container.appendChild(chip);
        });
      }
      state.stimulusReadyAt = Date.now();
      cardState.set(card.dataset.partId, state);
    } else if (taskType === "qa") {
      state.stimulusReadyAt = Date.now();
      cardState.set(card.dataset.partId, state);
      const questionText = card.dataset.questionText || "";
      speak(questionText, () => {});
    }
  }

  // ── 録音中の音量メーター + 発話開始検知（応答速度の計測） ──────
  function setupVadMeter(card, stream, state) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const bar = card.querySelector("[data-volume-bar]");
    if (!AudioCtx) return null;

    let ctx;
    try {
      ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.5;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      let rafId = null;

      const tick = () => {
        analyser.getByteTimeDomainData(dataArray);
        let sumSquares = 0;
        for (let i = 0; i < dataArray.length; i += 1) {
          const v = (dataArray[i] - 128) / 128;
          sumSquares += v * v;
        }
        const rms = Math.sqrt(sumSquares / dataArray.length);
        if (bar) bar.style.width = `${Math.round(Math.min(1, rms * 4) * 100)}%`;

        if (!state.speechOnsetAt && rms >= VAD_THRESHOLD) {
          state.speechOnsetAt = Date.now();
        }
        rafId = requestAnimationFrame(tick);
      };
      tick();

      return {
        stop() {
          if (rafId) cancelAnimationFrame(rafId);
          try { source.disconnect(); } catch (_) { /* ignore */ }
          try { analyser.disconnect(); } catch (_) { /* ignore */ }
          try { ctx.close(); } catch (_) { /* ignore */ }
          if (bar) bar.style.width = "0%";
        },
      };
    } catch (_) {
      if (ctx) {
        try { ctx.close(); } catch (_) { /* ignore */ }
      }
      return null;
    }
  }

  function formatSeconds(totalSeconds) {
    const sec = Math.max(0, Math.floor(totalSeconds || 0));
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function startQaCountdown(card, state) {
    const timeLimit = Number(card.dataset.timeLimit || 15);
    const timerEl = card.querySelector("[data-timer]");
    if (!timerEl) return;
    const startedAt = Date.now();

    state.timerIntervalId = setInterval(() => {
      const elapsed = (Date.now() - startedAt) / 1000;
      const remaining = timeLimit - elapsed;
      timerEl.textContent = formatSeconds(Math.max(0, remaining));
      timerEl.classList.toggle("text-rose-600", remaining <= 3);
      if (remaining <= 0) {
        clearInterval(state.timerIntervalId);
        state.timerIntervalId = null;
        handleStopClick(card);
      }
    }, 200);
  }

  function stopQaCountdown(state) {
    if (state.timerIntervalId) {
      clearInterval(state.timerIntervalId);
      state.timerIntervalId = null;
    }
  }

  async function handleRecordClick(card) {
    const partId = card.dataset.partId;
    if (activeRecordingPart) return;
    setError(card, "");
    micErrorBanner.classList.add("hidden");

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError(card, "このブラウザはマイク録音に対応していません。別のブラウザでお試しください。");
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      setError(card, "マイクへのアクセスが許可されませんでした。ブラウザの設定を確認し、もう一度お試しください。");
      return;
    }

    const state = cardState.get(partId) || {};
    state.speechOnsetAt = null;
    state.mediaStream = stream;
    state.recordingStartedAt = Date.now();

    const mimeType = pickMimeType();
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    const chunks = [];

    recorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    });

    recorder.addEventListener("stop", () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
      const onsetAt = state.speechOnsetAt || state.recordingStartedAt;
      const stimulusReadyAt = state.stimulusReadyAt || state.recordingStartedAt;
      const latencyMs = Math.max(0, onsetAt - stimulusReadyAt);
      uploadAudio(card, blob, mimeType || "audio/webm", latencyMs);
    });

    recorder.addEventListener("error", () => {
      setError(card, "録音中にエラーが発生しました。もう一度お試しください。");
      cleanupRecording(card, partId);
      activeRecordingPart = null;
      updateRecordButtonStates();
    });

    state.recorder = recorder;
    state.vadMeter = setupVadMeter(card, stream, state);
    cardState.set(partId, state);

    activeRecordingPart = partId;
    updateRecordButtonStates();

    card.dataset.status = "recording";
    renderCard(card);
    card.querySelector("[data-live-monitor]")?.classList.remove("hidden");

    try {
      recorder.start();
    } catch (err) {
      setError(card, "録音を開始できませんでした。もう一度お試しください。");
      cleanupRecording(card, partId);
      activeRecordingPart = null;
      updateRecordButtonStates();
      card.dataset.status = "not_started";
      renderCard(card);
      return;
    }

    if (card.dataset.taskType === "qa") {
      startQaCountdown(card, state);
    }
  }

  function cleanupRecording(card, partId) {
    const state = cardState.get(partId) || {};
    stopQaCountdown(state);
    if (state.vadMeter) {
      state.vadMeter.stop();
      state.vadMeter = null;
    }
    cardState.set(partId, state);
    card.querySelector("[data-live-monitor]")?.classList.add("hidden");
  }

  function handleStopClick(card) {
    const partId = card.dataset.partId;
    const state = cardState.get(partId) || {};
    if (!state.recorder || state.recorder.state === "inactive") return;

    cleanupRecording(card, partId);
    activeRecordingPart = null;
    updateRecordButtonStates();

    card.dataset.status = "transcribing";
    renderCard(card);
    state.recorder.stop();
  }

  async function uploadAudio(card, blob, mimeType, latencyMs) {
    const partId = card.dataset.partId;
    const formData = new FormData();
    formData.append("audio", blob, `${partId}.${extensionFor(mimeType)}`);
    formData.append("response_latency_ms", String(Math.round(latencyMs)));

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    try {
      const res = await fetch(`/level_check/api/sessions/${SESSION_ID}/parts/${partId}/audio`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const data = await res.json();

      if (!res.ok || !data.ok) {
        card.dataset.status = "error";
        renderCard(card);
        setError(card, data.error || "アップロードに失敗しました。「やり直す」から再度お試しください。");
        return;
      }

      card.dataset.status = data.part.status || "transcribing";
      setError(card, "");
      renderCard(card);
      startStatusPolling(card);
    } catch (err) {
      clearTimeout(timeoutId);
      card.dataset.status = "error";
      renderCard(card);
      const msg =
        err.name === "AbortError"
          ? "アップロードがタイムアウトしました。ネットワークをご確認のうえ、やり直してください。"
          : "アップロードに失敗しました。ネットワークをご確認のうえ、やり直してください。";
      setError(card, msg);
    }
  }

  function startStatusPolling(card) {
    const partId = card.dataset.partId;
    const state = cardState.get(partId) || {};
    if (state.pollIntervalId) return;

    state.pollIntervalId = setInterval(async () => {
      try {
        const res = await fetch(`/level_check/api/sessions/${SESSION_ID}/parts/${partId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data.ok) return;
        const part = data.part;

        if (part.status === card.dataset.status) return;
        card.dataset.status = part.status;
        renderCard(card);

        if (part.status === "done" || part.status === "error") {
          stopStatusPolling(partId);
          if (part.transcript_error) setError(card, part.transcript_error);
        }
      } catch (_) {
        // ネットワーク不調時は次回のポーリングで再試行
      }
    }, 2500);
    cardState.set(partId, state);
  }

  function stopStatusPolling(partId) {
    const state = cardState.get(partId) || {};
    if (state.pollIntervalId) {
      clearInterval(state.pollIntervalId);
      state.pollIntervalId = null;
    }
    cardState.set(partId, state);
  }

  async function handleRetryClick(card) {
    const partId = card.dataset.partId;
    try {
      const res = await fetch(`/level_check/api/sessions/${SESSION_ID}/parts/${partId}/retry`, { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "リセットに失敗しました。");

      card.dataset.status = "not_started";
      setError(card, "");
      renderCard(card);
      setupStimulus(card);
    } catch (err) {
      setError(card, err.message);
    }
  }

  cards.forEach((card) => {
    cardState.set(card.dataset.partId, {});
    card.querySelector(".btn-record")?.addEventListener("click", () => handleRecordClick(card));
    card.querySelector(".btn-stop")?.addEventListener("click", () => handleStopClick(card));
    card.querySelector(".btn-retry")?.addEventListener("click", () => handleRetryClick(card));

    if (card.dataset.status === "not_started") {
      setupStimulus(card);
    } else if (card.dataset.status === "transcribing" || card.dataset.status === "scoring") {
      startStatusPolling(card);
    }
    renderCard(card);
  });

  window.addEventListener("beforeunload", (event) => {
    if (activeRecordingPart) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  refreshOverallProgress();
})();
