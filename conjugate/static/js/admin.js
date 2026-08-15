(() => {
  const form = document.getElementById("settings-form");
  const btn = document.getElementById("save-btn");
  const messageEl = document.getElementById("save-message");
  const bgIdInput = document.getElementById("background-id");
  const bgOpacityInput = document.getElementById("background-opacity");
  const bgSlider = document.getElementById("bg-opacity-slider");
  const bgOpacityValue = document.getElementById("bg-opacity-value");
  const bgLabel = document.getElementById("bg-current-label");
  const pageBg = document.getElementById("page-bg-layer");
  if (!form) return;

  function showMessage(message, isError) {
    messageEl.textContent = message;
    messageEl.className = `text-sm mt-2 ${isError ? "text-rose-600" : "text-emerald-600"}`;
    messageEl.classList.remove("hidden");
  }

  function applyBackgroundPreview(imageUrl, opacity) {
    if (!pageBg) return;
    if (imageUrl) pageBg.style.backgroundImage = `url('${imageUrl}')`;
    if (typeof opacity === "number") pageBg.style.opacity = String(opacity);
  }

  document.querySelectorAll(".vsc-bg-pick").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".vsc-bg-pick").forEach((el) => el.classList.remove("vsc-bg-pick-active"));
      button.classList.add("vsc-bg-pick-active");
      if (bgIdInput) bgIdInput.value = button.dataset.bgId || "";
      if (bgLabel) bgLabel.textContent = button.dataset.bgLabel || "";
      applyBackgroundPreview(button.dataset.bgImage, undefined);
    });
  });

  if (bgSlider) {
    bgSlider.addEventListener("input", () => {
      const opacity = Math.max(0, Math.min(100, parseInt(bgSlider.value, 10) || 0)) / 100;
      if (bgOpacityValue) bgOpacityValue.textContent = String(Math.round(opacity * 100));
      if (bgOpacityInput) bgOpacityInput.value = String(opacity);
      applyBackgroundPreview(undefined, opacity);
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const enabledCategories = Array.from(form.querySelectorAll('input[name="enabled_categories"]:checked')).map((el) => el.value);
    const enabledTenses = Array.from(form.querySelectorAll('input[name="enabled_tenses"]:checked')).map((el) => el.value);

    const payload = {
      enabled_categories: enabledCategories,
      enabled_tenses: enabledTenses,
      asr_engine: form.querySelector('select[name="asr_engine"]').value,
      whisper_model: form.querySelector('select[name="whisper_model"]').value,
      strictness: form.querySelector('select[name="strictness"]').value,
      targets_per_question: parseInt(form.querySelector('select[name="targets_per_question"]').value, 10),
      questions_per_session: parseInt(form.querySelector('input[name="questions_per_session"]').value, 10),
      prioritize_weak_verbs: form.querySelector('input[name="prioritize_weak_verbs"]').checked,
      gustar_enabled: form.querySelector('input[name="gustar_enabled"]').checked,
      gustar_per_session: parseInt(form.querySelector('input[name="gustar_per_session"]').value, 10),
      background_id: bgIdInput ? bgIdInput.value : "meadow",
      background_opacity: bgOpacityInput ? parseFloat(bgOpacityInput.value) : 0.38,
      opening_enabled: form.querySelector('input[name="opening_enabled"]').checked,
      opening_ms: parseInt(form.querySelector('input[name="opening_ms"]').value, 10),
      admin_password: form.querySelector('input[name="admin_password"]').value,
    };

    btn.disabled = true;
    btn.textContent = "保存中...";
    messageEl.classList.add("hidden");

    try {
      const res = await fetch("/conjugate/admin/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "保存に失敗しました。");
      showMessage("設定を保存しました。", false);
      form.querySelector('input[name="admin_password"]').value = "";
    } catch (err) {
      showMessage(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "設定を保存";
    }
  });
})();
