(() => {
  const form = document.getElementById("start-form");
  const errorBox = document.getElementById("start-error");
  const startBtn = document.getElementById("start-btn");

  if (!form) return;

  function showError(message) {
    if (!message) {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
      return;
    }
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    startBtn.disabled = true;
    startBtn.textContent = "準備中...";

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
          startBtn.disabled = false;
          startBtn.textContent = "テストを開始する";
          return;
        }
      } else {
        showError("このブラウザはマイク録音に対応していません。別のブラウザでお試しください。");
        startBtn.disabled = false;
        startBtn.textContent = "テストを開始する";
        return;
      }

      const res = await fetch("/level_check/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "開始に失敗しました。");
      window.location.href = `/level_check/session/${data.session_id}`;
    } catch (err) {
      showError(err.message || "開始に失敗しました。もう一度お試しください。");
      startBtn.disabled = false;
      startBtn.textContent = "テストを開始する";
    }
  });
})();
