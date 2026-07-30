(() => {
  const SESSION_ID = window.DEBATE_SESSION_ID;
  const PART = window.DEBATE_PART;

  const textarea = document.getElementById("transcript-edited");
  const confirmBtn = document.getElementById("confirm-btn");
  const redoBtn = document.getElementById("redo-btn");
  const errorBox = document.getElementById("review-error");

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
  }

  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    confirmBtn.textContent = "保存中...";
    errorBox.classList.add("hidden");

    try {
      const res = await fetch(`/debate/api/sessions/${SESSION_ID}/parts/${PART}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript_edited: textarea.value }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "保存に失敗しました。");

      window.location.href = `/debate/session/${SESSION_ID}`;
    } catch (err) {
      showError(err.message);
      confirmBtn.disabled = false;
      confirmBtn.textContent = "保存して確定";
    }
  });

  redoBtn.addEventListener("click", async () => {
    if (!window.confirm(`${PART} パートの録音・文字起こしをリセットしてやり直しますか？`)) return;

    redoBtn.disabled = true;
    try {
      const res = await fetch(`/debate/api/sessions/${SESSION_ID}/parts/${PART}/reset`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "リセットに失敗しました。");

      window.location.href = `/debate/session/${SESSION_ID}`;
    } catch (err) {
      showError(err.message);
      redoBtn.disabled = false;
    }
  });
})();
