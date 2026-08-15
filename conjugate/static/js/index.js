(() => {
  const openingOverlay = document.getElementById("opening-overlay");
  if (openingOverlay) {
    const openingMs = Math.max(400, Number(window.CONJUGATE_OPENING_MS || 2000));
    openingOverlay.style.setProperty("--splash-ms", `${openingMs}ms`);
    setTimeout(() => openingOverlay.remove(), openingMs + 40);
  }

  const form = document.getElementById("start-form");
  const btn = document.getElementById("start-btn");
  const errorEl = document.getElementById("start-error");

  if (!form) return;

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove("hidden");
  }

  function selectedTenses() {
    return Array.from(form.querySelectorAll('input[name="tense"]:checked')).map((el) => el.value);
  }

  function selectedCount() {
    const select = form.querySelector('select[name="count"]');
    return parseInt(select.value, 10);
  }

  function selectedCategories() {
    return Array.from(form.querySelectorAll('input[name="category"]:checked')).map((el) => el.value);
  }

  async function startSession({ categories, tenses, count, prioritizeWeak, label }) {
    errorEl.classList.add("hidden");
    if (!categories.length) {
      showError("出題カテゴリを1つ以上選んでください。");
      return;
    }
    if (!tenses.length) {
      showError("出題する文型を1つ以上選んでください。");
      return;
    }

    const original = btn.textContent;
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
      btn.textContent = label || original || "今日の練習を始める";
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await startSession({
      categories: selectedCategories(),
      tenses: selectedTenses(),
      count: selectedCount(),
      prioritizeWeak: form.querySelector('input[name="prioritize_weak_verbs"]').checked,
      label: "今日の練習を始める",
    });
  });

  document.querySelectorAll("[data-start]").forEach((el) => {
    el.addEventListener("click", async () => {
      const mode = el.dataset.start;
      const tenses = selectedTenses();
      const count = selectedCount();
      if (mode === "review") {
        await startSession({
          categories: selectedCategories(),
          tenses,
          count,
          prioritizeWeak: true,
          label: "今日の練習を始める",
        });
        return;
      }
      if (mode === "motion") {
        await startSession({
          categories: ["motion_daily"],
          tenses,
          count,
          prioritizeWeak: false,
          label: "今日の練習を始める",
        });
        return;
      }
      if (mode === "category") {
        await startSession({
          categories: [el.dataset.category],
          tenses,
          count,
          prioritizeWeak: false,
          label: "今日の練習を始める",
        });
      }
    });
  });
})();
