(() => {
  const progress = Object.assign(
    {
      coins: 0,
      guardian_count: 0,
      guardian_price: 50,
      guardian_coins_needed: 50,
      can_afford_guardian: false,
    },
    window.CONJUGATE_PROGRESS || {}
  );

  const buyBtn = document.getElementById("buy-guardian-btn");
  if (!buyBtn) return;

  const hintEl = document.getElementById("guardian-hint");
  const messageEl = document.getElementById("guardian-message");
  const countEl = document.getElementById("guardian-count");
  const balanceEl = document.getElementById("shop-balance");

  function refreshUi() {
    buyBtn.textContent = `🪙${progress.guardian_price}で交換する`;
    buyBtn.disabled = !progress.can_afford_guardian;
    if (countEl) countEl.textContent = String(progress.guardian_count);
    if (balanceEl) balanceEl.textContent = `🪙 ${progress.coins}`;
    if (hintEl) {
      if (progress.can_afford_guardian) {
        hintEl.classList.add("hidden");
      } else {
        hintEl.textContent = `あと🪙${progress.guardian_coins_needed}枚必要です。`;
        hintEl.classList.remove("hidden");
      }
    }
  }

  function showMessage(message, isError) {
    if (!messageEl) return;
    messageEl.textContent = message;
    messageEl.style.color = isError ? "var(--danger-text)" : "var(--ok-text)";
    messageEl.classList.remove("hidden");
  }

  buyBtn.addEventListener("click", async () => {
    if (buyBtn.disabled) return;
    buyBtn.disabled = true;
    const originalLabel = buyBtn.textContent;
    buyBtn.textContent = "交換中...";
    try {
      const res = await fetch("/conjugate/api/progress/guardian/purchase", { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "交換に失敗しました。");
      Object.assign(progress, data.progress || {});
      showMessage("Guardiánと交換しました！", false);
      refreshUi();
      if (window.vscCelebrateFromResult) window.vscCelebrateFromResult({ newly_mastered: true });
    } catch (err) {
      showMessage(err.message, true);
      buyBtn.textContent = originalLabel;
      buyBtn.disabled = !progress.can_afford_guardian;
    }
  });

  refreshUi();
})();
