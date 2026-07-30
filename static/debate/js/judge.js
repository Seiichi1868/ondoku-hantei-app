(() => {
  const SESSION_ID = window.DEBATE_SESSION_ID;
  const STATUS = window.DEBATE_JUDGE_STATUS;

  const runBtn = document.getElementById("run-judge-btn");
  const errorBox = document.getElementById("run-judge-error");

  function showError(message) {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
  }

  async function triggerJudge() {
    if (!runBtn) return;
    runBtn.disabled = true;
    const originalLabel = runBtn.textContent;
    runBtn.textContent = "ジャッジを開始しています...";
    if (errorBox) errorBox.classList.add("hidden");

    try {
      const res = await fetch(`/debate/api/sessions/${SESSION_ID}/judge`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "ジャッジの開始に失敗しました。");
      window.location.reload();
    } catch (err) {
      runBtn.disabled = false;
      runBtn.textContent = originalLabel;
      showError(err.message);
    }
  }

  runBtn?.addEventListener("click", triggerJudge);

  // ── 実行中のポーリング（完了したら画面を再読み込みして結果を表示） ──────
  if (STATUS === "judging") {
    const pollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/debate/api/sessions/${SESSION_ID}/judge`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status && data.status !== "judging") {
          clearInterval(pollTimer);
          window.location.reload();
        }
      } catch (_) {
        // ネットワーク不調時は次回のポーリングで再試行する
      }
    }, 3000);
  }
})();
