(() => {
  const SESSION_ID = window.CONJUGATE_SESSION_ID;
  const ASR_ENGINE = window.CONJUGATE_ASR_ENGINE || "whisper";
  const TENSE_LABELS = window.CONJUGATE_TENSE_LABELS || {};
  const CATEGORY_LABELS = window.CONJUGATE_CATEGORY_LABELS || {};
  const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];

  const progressLabel = document.getElementById("progress-label");
  const micErrorBanner = document.getElementById("mic-error-banner");
  const categoryPill = document.getElementById("category-pill");
  const tenseTargetPill = document.getElementById("tense-target-pill");
  const verbHeaderBlock = document.getElementById("verb-header-block");
  const gustarHeaderBlock = document.getElementById("gustar-header-block");
  const infinitiveTitle = document.getElementById("infinitive-title");
  const meaningJa = document.getElementById("meaning-ja");
  const verbNote = document.getElementById("verb-note");
  const gustarTopic = document.getElementById("gustar-topic");
  const sentenceList = document.getElementById("sentence-list");
  const targetStepper = document.getElementById("target-stepper");
  const recordBtn = document.getElementById("record-btn");
  const stopBtn = document.getElementById("stop-btn");
  const recordingStatus = document.getElementById("recording-status");
  const feedbackBox = document.getElementById("feedback-box");
  const nextBtn = document.getElementById("next-btn");
  const volumeMeter = document.getElementById("volume-meter");
  const volumeBar = document.getElementById("volume-bar");

  let session = null;
  let questionIndex = 0;
  let targetIndex = 0;
  let mediaRecorder = null;
  let mediaStream = null;
  let speechRecognizer = null;

  function useWebSpeech() {
    return ASR_ENGINE === "web_speech" && (window.SpeechRecognition || window.webkitSpeechRecognition);
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

  async function loadSession() {
    const res = await fetch(`/conjugate/api/sessions/${SESSION_ID}`);
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "セッションの取得に失敗しました。");
    session = data.session;
  }

  function currentQuestion() {
    return session.questions[questionIndex];
  }

  function currentTarget() {
    const q = currentQuestion();
    return q.targets[targetIndex];
  }

  function updateProgress() {
    progressLabel.textContent = `${questionIndex + 1}/${session.questions.length}問`;
  }

  function renderTargetStepper(q) {
    targetStepper.innerHTML = "";
    if (q.targets.length <= 1) return;
    q.targets.forEach((t, i) => {
      const dot = document.createElement("span");
      const label = q.kind === "gustar" ? "gustar" : (TENSE_LABELS[t] || t);
      dot.textContent = label;
      dot.className = `vsc-step-dot ${i === targetIndex ? "vsc-step-dot-active" : i < targetIndex ? "vsc-step-dot-done" : ""}`;
      targetStepper.appendChild(dot);
    });
  }

  function renderQuestion() {
    const q = currentQuestion();
    feedbackBox.classList.add("hidden");
    feedbackBox.innerHTML = "";
    nextBtn.classList.add("hidden");
    recordBtn.classList.remove("hidden");
    stopBtn.classList.add("hidden");
    recordingStatus.textContent = "";
    updateProgress();
    renderTargetStepper(q);

    if (q.kind === "gustar") {
      verbHeaderBlock.classList.add("hidden");
      gustarHeaderBlock.classList.remove("hidden");
      gustarTopic.textContent = q.topic_ja;
      categoryPill.textContent = "特殊構文編";
      tenseTargetPill.textContent = "gustar";

      sentenceList.innerHTML = "";
      const li = document.createElement("li");
      li.className = "vsc-form-item vsc-form-item-target";
      li.innerHTML = `<span class="vsc-form-bullet"></span><span>${q.yo_sentence}</span>`;
      sentenceList.appendChild(li);
    } else {
      verbHeaderBlock.classList.remove("hidden");
      gustarHeaderBlock.classList.add("hidden");
      infinitiveTitle.textContent = q.infinitive.toUpperCase();
      meaningJa.textContent = q.meaning_ja;
      if (q.note) {
        verbNote.textContent = `💡 ${q.note}`;
        verbNote.classList.remove("hidden");
      } else {
        verbNote.classList.add("hidden");
      }
      categoryPill.textContent = CATEGORY_LABELS[q.category] || q.category;

      const target = currentTarget();
      tenseTargetPill.textContent = `→ ${TENSE_LABELS[target] || target} に変換`;

      sentenceList.innerHTML = "";
      Object.keys(q.forms).forEach((tense) => {
        const li = document.createElement("li");
        const isTarget = q.targets.includes(tense);
        const isCurrentTarget = tense === target;
        li.className = `vsc-form-item ${isTarget ? "vsc-form-item-target" : ""} ${isCurrentTarget ? "vsc-form-item-active" : ""}`;
        const badge = isTarget ? `<span class="vsc-mini-badge">${isCurrentTarget ? "今回の対象" : "対象"}</span>` : "";
        li.innerHTML = `<span class="vsc-form-bullet"></span><span>${q.forms[tense].yo}</span>${badge}`;
        sentenceList.appendChild(li);
      });
    }
  }

  function setMicError(message) {
    if (!message) {
      micErrorBanner.classList.add("hidden");
      micErrorBanner.textContent = "";
      return;
    }
    micErrorBanner.textContent = message;
    micErrorBanner.classList.remove("hidden");
  }

  function levelInfo(level) {
    const map = {
      correct: { label: "正解！", cls: "vsc-feedback-correct" },
      pronoun_error: { label: "惜しい（代名詞ミス）", cls: "vsc-feedback-warn" },
      conjugation_error: { label: "活用形が違います", cls: "vsc-feedback-warn" },
      way_off: { label: "全く違います", cls: "vsc-feedback-bad" },
    };
    return map[level] || map.way_off;
  }

  function showFeedback(result) {
    const info = levelInfo(result.level);
    feedbackBox.className = `mt-4 vsc-feedback ${info.cls}`;
    feedbackBox.innerHTML = `
      <div class="font-bold">${info.label}</div>
      <div class="text-sm mt-1">${result.message}</div>
      ${result.newly_mastered ? '<div class="vsc-mastered-toast">習得バッジを獲得！</div>' : ""}
      <div class="text-xs mt-2" style="color: var(--text-secondary);">認識結果: 「${result.transcript || "（認識できませんでした）"}」</div>
    `;
    feedbackBox.classList.remove("hidden");
  }

  async function submitAnswer({ audioBlob, mimeType, transcript }) {
    const q = currentQuestion();
    const target = currentTarget();
    const url = `/conjugate/api/sessions/${SESSION_ID}/questions/${q.question_id}/targets/${target}/answer`;

    const formData = new FormData();
    if (audioBlob) {
      formData.append("audio", audioBlob, `answer.${extensionFor(mimeType || "audio/webm")}`);
    } else {
      formData.append("transcript", transcript || "");
    }

    recordingStatus.textContent = "判定中...";
    const res = await fetch(url, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "採点に失敗しました。");
    recordingStatus.textContent = "";
    showFeedback(data.result);

    recordBtn.classList.add("hidden");
    stopBtn.classList.add("hidden");
    nextBtn.classList.remove("hidden");
    nextBtn.textContent = isLastTargetOfQuestion() ? (isLastQuestion() ? "結果を見る →" : "次の問題へ →") : "次の文型へ →";
  }

  function isLastTargetOfQuestion() {
    const q = currentQuestion();
    return targetIndex >= q.targets.length - 1;
  }

  function isLastQuestion() {
    return questionIndex >= session.questions.length - 1;
  }

  async function handleNext() {
    if (!isLastTargetOfQuestion()) {
      targetIndex += 1;
      renderQuestion();
      return;
    }
    if (!isLastQuestion()) {
      questionIndex += 1;
      targetIndex = 0;
      renderQuestion();
      return;
    }
    await finishSession();
  }

  async function finishSession() {
    nextBtn.disabled = true;
    nextBtn.textContent = "集計中...";
    try {
      await fetch(`/conjugate/api/sessions/${SESSION_ID}/finish`, { method: "POST" });
    } catch (_) {
      // ネットワーク不調でもサマリ画面側で再計算されるため続行する
    }
    window.location.href = `/conjugate/session/${SESSION_ID}/summary`;
  }

  function setupVolumeMeter(stream) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return null;
    try {
      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
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
        volumeBar.style.width = `${Math.round(Math.min(1, rms * 4) * 100)}%`;
        rafId = requestAnimationFrame(tick);
      };
      tick();

      return {
        stop() {
          if (rafId) cancelAnimationFrame(rafId);
          try { source.disconnect(); } catch (_) { /* ignore */ }
          try { analyser.disconnect(); } catch (_) { /* ignore */ }
          try { ctx.close(); } catch (_) { /* ignore */ }
          volumeBar.style.width = "0%";
        },
      };
    } catch (_) {
      return null;
    }
  }

  async function startRecordingWithMediaRecorder() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setMicError("このブラウザはマイク録音に対応していません。別のブラウザでお試しください。");
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (_) {
      setMicError("マイクへのアクセスが許可されませんでした。ブラウザの設定を確認してください。");
      return;
    }
    setMicError("");
    mediaStream = stream;
    const mimeType = pickMimeType();
    mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    const chunks = [];
    const volMeter = setupVolumeMeter(stream);
    volumeMeter.classList.remove("hidden");

    mediaRecorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    });
    mediaRecorder.addEventListener("stop", async () => {
      stream.getTracks().forEach((t) => t.stop());
      if (volMeter) volMeter.stop();
      volumeMeter.classList.add("hidden");
      const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
      try {
        await submitAnswer({ audioBlob: blob, mimeType: mimeType || "audio/webm" });
      } catch (err) {
        recordingStatus.textContent = "";
        setMicError(err.message);
        recordBtn.classList.remove("hidden");
      }
    });

    recordBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
    recordingStatus.textContent = "録音中... 発話が終わったら「録音を終了」を押してください。";
    mediaRecorder.start();
  }

  function stopRecordingWithMediaRecorder() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      recordingStatus.textContent = "アップロード中...";
      mediaRecorder.stop();
    }
  }

  function startRecordingWithWebSpeech() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    speechRecognizer = new Recognition();
    speechRecognizer.lang = "es-ES";
    speechRecognizer.interimResults = false;
    speechRecognizer.maxAlternatives = 1;
    speechRecognizer.continuous = false;

    recordBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
    recordingStatus.textContent = "録音中（低遅延モード）... 発話が終わると自動で判定します。";

    speechRecognizer.addEventListener("result", async (event) => {
      const transcript = event.results[0][0].transcript;
      stopBtn.classList.add("hidden");
      try {
        await submitAnswer({ transcript });
      } catch (err) {
        recordingStatus.textContent = "";
        setMicError(err.message);
        recordBtn.classList.remove("hidden");
      }
    });
    speechRecognizer.addEventListener("error", () => {
      recordingStatus.textContent = "";
      stopBtn.classList.add("hidden");
      recordBtn.classList.remove("hidden");
      setMicError("音声認識でエラーが発生しました。もう一度お試しください。");
    });
    speechRecognizer.addEventListener("end", () => {
      stopBtn.classList.add("hidden");
    });

    try {
      speechRecognizer.start();
    } catch (_) {
      setMicError("音声認識を開始できませんでした。");
      recordBtn.classList.remove("hidden");
      stopBtn.classList.add("hidden");
    }
  }

  function handleRecordClick() {
    setMicError("");
    feedbackBox.classList.add("hidden");
    if (useWebSpeech()) {
      startRecordingWithWebSpeech();
    } else {
      startRecordingWithMediaRecorder();
    }
  }

  function handleStopClick() {
    if (useWebSpeech() && speechRecognizer) {
      speechRecognizer.stop();
    } else {
      stopRecordingWithMediaRecorder();
    }
  }

  recordBtn.addEventListener("click", handleRecordClick);
  stopBtn.addEventListener("click", handleStopClick);
  nextBtn.addEventListener("click", handleNext);

  (async () => {
    try {
      await loadSession();
      if (!session.questions.length) throw new Error("出題できる問題がありません。");
      if (session.status === "done") {
        window.location.href = `/conjugate/session/${SESSION_ID}/summary`;
        return;
      }
      renderQuestion();
    } catch (err) {
      setMicError(err.message);
    }
  })();

  window.addEventListener("beforeunload", (event) => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      event.preventDefault();
      event.returnValue = "";
    }
  });
})();
