(() => {
  const form = document.getElementById("start-form");
  const btn = document.getElementById("start-btn");
  const errorEl = document.getElementById("start-error");

  if (!form) return;

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove("hidden");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.classList.add("hidden");

    const categories = Array.from(form.querySelectorAll('input[name="category"]:checked')).map((el) => el.value);
    const tenses = Array.from(form.querySelectorAll('input[name="tense"]:checked')).map((el) => el.value);
    const count = parseInt(form.querySelector('select[name="count"]').value, 10);
    const prioritizeWeak = form.querySelector('input[name="prioritize_weak_verbs"]').checked;

    if (!categories.length) {
      showError("出題カテゴリを1つ以上選んでください。");
      return;
    }
    if (!tenses.length) {
      showError("出題する文型を1つ以上選んでください。");
      return;
    }

    btn.disabled = true;
    btn.textContent = "準備中...";

    try {
      const res = await fetch("/conjugate/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          categories,
          tenses,
          count,
          prioritize_weak_verbs: prioritizeWeak,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "セッションの作成に失敗しました。");
      window.location.href = `/conjugate/session/${data.session_id}`;
    } catch (err) {
      showError(err.message);
      btn.disabled = false;
      btn.textContent = "練習を始める";
    }
  });
})();
