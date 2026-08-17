(() => {
  const COLORS = ["#7CB342", "#689F38", "#C8E6A0", "#FFFFFF", "#F4F7EE", "#D7EFC3"];
  const PARTICLE_COUNT = 28;
  const CONFETTI_MS = 1800;
  const COUNT_MS = 600;
  const LEAVE_MS = 220;

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function easeOutCubic(t) {
    return 1 - (1 - t) ** 3;
  }

  function celebrate() {
    if (prefersReducedMotion()) return;
    const root = document.createElement("div");
    root.className = "vsc-confetti";
    root.setAttribute("aria-hidden", "true");
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < PARTICLE_COUNT; i += 1) {
      const piece = document.createElement("span");
      piece.className = "vsc-confetti-piece";
      const x = 8 + Math.random() * 84;
      const delay = Math.random() * 220;
      const duration = 1200 + Math.random() * 600;
      const drift = (Math.random() - 0.5) * 120;
      const rot = 180 + Math.random() * 540;
      const w = 5 + Math.random() * 5;
      const h = 8 + Math.random() * 7;
      piece.style.left = `${x}vw`;
      piece.style.width = `${w}px`;
      piece.style.height = `${h}px`;
      piece.style.background = COLORS[i % COLORS.length];
      piece.style.animationDelay = `${delay}ms`;
      piece.style.animationDuration = `${duration}ms`;
      piece.style.setProperty("--vsc-drift", `${drift}px`);
      piece.style.setProperty("--vsc-rot", `${rot}deg`);
      fragment.appendChild(piece);
    }
    root.appendChild(fragment);
    document.body.appendChild(root);
    window.setTimeout(() => root.remove(), CONFETTI_MS + 80);
  }

  function celebrateFromResult(result) {
    if (!result) return;
    const progress = result.progress || {};
    if (result.newly_mastered || progress.newly_mastered || progress.streak_incremented) {
      celebrate();
    }
  }

  function countUp(el, toValue, duration) {
    if (!el) return;
    const to = Number(toValue);
    if (!Number.isFinite(to)) return;
    if (prefersReducedMotion()) {
      el.textContent = String(to);
      return;
    }
    const from = Number(el.textContent);
    const start = Number.isFinite(from) ? from : 0;
    if (start === to) {
      el.textContent = String(to);
      return;
    }
    const ms = duration || COUNT_MS;
    const begun = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - begun) / ms);
      const value = Math.round(start + (to - start) * easeOutCubic(t));
      el.textContent = String(value);
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  function setProgressRing(el, percent) {
    if (!el) return;
    const value = Math.max(0, Math.min(100, Number(percent) || 0));
    const offset = 100 - value;
    if (prefersReducedMotion()) {
      el.style.transition = "none";
    }
    requestAnimationFrame(() => {
      el.style.strokeDashoffset = String(offset);
    });
  }

  function navigate(url) {
    if (!url) return;
    if (prefersReducedMotion() || document.body.classList.contains("vsc-page-leave")) {
      window.location.href = url;
      return;
    }
    document.body.classList.add("vsc-page-leave");
    window.setTimeout(() => {
      window.location.href = url;
    }, LEAVE_MS);
  }

  function initCountUps() {
    document.querySelectorAll("[data-count-up]").forEach((el) => {
      const to = el.getAttribute("data-count-to");
      countUp(el, to);
    });
  }

  function initProgressRings() {
    document.querySelectorAll("[data-progress-ring]").forEach((el) => {
      setProgressRing(el, el.getAttribute("data-progress-ring"));
    });
  }

  function isInternalConjugateLink(anchor) {
    if (!anchor || !anchor.getAttribute) return false;
    if (anchor.target && anchor.target !== "_self") return false;
    if (anchor.hasAttribute("download")) return false;
    const href = anchor.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return false;
    let url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (_) {
      return false;
    }
    if (url.origin !== window.location.origin) return false;
    if (url.pathname.indexOf("/conjugate") !== 0) return false;
    if (url.pathname === window.location.pathname && url.search === window.location.search) return false;
    return true;
  }

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const anchor = event.target.closest("a[href]");
    if (!isInternalConjugateLink(anchor)) return;
    event.preventDefault();
    navigate(anchor.href);
  });

  function startVisualFx() {
    initCountUps();
    initProgressRings();
  }

  function scheduleVisualFx() {
    const overlay = document.getElementById("opening-overlay");
    const skip = document.documentElement.classList.contains("vsc-skip-opening");
    if (overlay && !skip) {
      const ms = Math.max(400, Number(window.CONJUGATE_OPENING_MS || 2000));
      window.setTimeout(startVisualFx, ms);
      return;
    }
    startVisualFx();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleVisualFx);
  } else {
    scheduleVisualFx();
  }

  window.vscCelebrate = celebrate;
  window.vscCelebrateFromResult = celebrateFromResult;
  window.vscCountUp = countUp;
  window.vscSetProgressRing = setProgressRing;
  window.vscNavigate = navigate;
})();
