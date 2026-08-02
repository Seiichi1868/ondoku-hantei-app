(() => {
  const form = document.getElementById("start-form");
  const errorBox = document.getElementById("start-error");
  const startBtn = document.getElementById("start-btn");
  const prepPanel = document.getElementById("start-prep");
  const prepBar = document.getElementById("start-prep-bar");
  const prepLabel = document.getElementById("start-prep-label");
  const prepPercent = document.getElementById("start-prep-percent");

  if (!form) return;

  // TTS 生成などを含むセッション作成の目安（秒）。実時間に応じて伸びを抑える。
  const ESTIMATED_PREP_MS = 12000;
  const PREP_LABELS = [
    { at: 0, text: "マイクを確認しています…" },
    { at: 0.15, text: "問題を選んでいます…" },
    { at: 0.35, text: "音声を準備しています…" },
    { at: 0.7, text: "まもなく開始します…" },
  ];

  let prepRaf = null;
  let prepStartedAt = 0;

  function showError(message) {
    if (!message) {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
      return;
    }
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
  }

  function setPrepProgress(ratio) {
    const clamped = Math.max(0, Math.min(0.95, ratio));
    const pct = Math.round(clamped * 100);
    if (prepBar) prepBar.style.width = `${pct}%`;
    if (prepPercent) prepPercent.textContent = `${pct}%`;
    if (prepLabel) {
      let label = PREP_LABELS[0].text;
      for (const item of PREP_LABELS) {
        if (clamped >= item.at) label = item.text;
      }
      prepLabel.textContent = label;
    }
  }

  function startPrepUi() {
    if (prepPanel) prepPanel.classList.remove("hidden");
    if (startBtn) startBtn.classList.add("hidden");
    prepStartedAt = performance.now();
    setPrepProgress(0.02);

    const tick = (now) => {
      const elapsed = now - prepStartedAt;
      // ease-out で伸び、完了直前で 95% に抑える（実完了で 100% へ）
      const t = Math.min(1, elapsed / ESTIMATED_PREP_MS);
      const eased = 1 - (1 - t) * (1 - t);
      setPrepProgress(0.02 + eased * 0.93);
      prepRaf = requestAnimationFrame(tick);
    };
    prepRaf = requestAnimationFrame(tick);
  }

  function finishPrepUi() {
    if (prepRaf) {
      cancelAnimationFrame(prepRaf);
      prepRaf = null;
    }
    if (prepBar) prepBar.style.width = "100%";
    if (prepPercent) prepPercent.textContent = "100%";
    if (prepLabel) prepLabel.textContent = "準備完了！移動します…";
  }

  function resetPrepUi() {
    if (prepRaf) {
      cancelAnimationFrame(prepRaf);
      prepRaf = null;
    }
    if (prepPanel) prepPanel.classList.add("hidden");
    if (startBtn) {
      startBtn.classList.remove("hidden");
      startBtn.disabled = false;
      startBtn.textContent = "テストを開始する";
    }
    setPrepProgress(0);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    startBtn.disabled = true;
    startPrepUi();

    const formData = new FormData(form);
    const payload = {
      class_name: formData.get("class_name") || "",
      number: formData.get("number") || "",
      name: formData.get("name") || "",
    };

    try {
      // マイク権限を先に確認しておく（開始直後に許可ダイアログで戸惑わないように）
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach((t) => t.stop());
        } catch (_) {
          showError("マイクへのアクセスが許可されませんでした。ブラウザの設定でマイクを許可してから、もう一度お試しください。");
          resetPrepUi();
          return;
        }
      } else {
        showError("このブラウザはマイク録音に対応していません。別のブラウザでお試しください。");
        resetPrepUi();
        return;
      }

      const res = await fetch("/level_check/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "開始に失敗しました。");
      finishPrepUi();
      // 完了バーが一瞬見えるようにしてから遷移
      await new Promise((r) => setTimeout(r, 280));
      window.location.href = `/level_check/session/${data.session_id}`;
    } catch (err) {
      showError(err.message || "開始に失敗しました。もう一度お試しください。");
      resetPrepUi();
    }
  });
})();
