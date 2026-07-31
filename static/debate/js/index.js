(() => {
  const openingOverlay = document.getElementById("opening-overlay");
  if (openingOverlay) {
    setTimeout(() => {
      openingOverlay.classList.add("opacity-0", "pointer-events-none", "transition-opacity", "duration-300");
      setTimeout(() => openingOverlay.remove(), 320);
    }, 1950);
  }

  const form = document.getElementById("motion-form");
  const motionInput = document.getElementById("motion-input");
  const speakerInput = document.getElementById("speaker-name-input");
  const startBtn = document.getElementById("start-btn");
  const errorBox = document.getElementById("form-error");

  document.querySelectorAll(".motion-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      motionInput.value = chip.dataset.motion || "";
      motionInput.focus();
    });
  });

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.classList.add("hidden");

    const motion = motionInput.value.trim();
    if (!motion) {
      showError("論題を入力してください。");
      return;
    }

    startBtn.disabled = true;
    startBtn.textContent = "作成中...";

    try {
      const response = await fetch("/debate/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          motion,
          speaker_name: speakerInput.value.trim(),
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "セッションの作成に失敗しました。");
      }

      window.location.href = `/debate/session/${data.session_id}`;
    } catch (err) {
      showError(err.message || "予期しないエラーが発生しました。");
      startBtn.disabled = false;
      startBtn.textContent = "ディベートを始める →";
    }
  });
})();
