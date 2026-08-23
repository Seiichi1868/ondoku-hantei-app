/**
 * 軽量サウンドエフェクトモジュール（Web Audio APIによる音声合成、外部ファイル不要）
 */
const SoundFX = (() => {
  const MUTE_KEY = "sfx_muted";
  const TAP_SELECTOR = [
    ".vsc-btn-primary",
    ".vsc-btn-secondary",
    ".vsc-btn-record",
    ".vsc-choice-btn",
    ".vsc-promo-btn",
    ".vsc-vocab-btn",
    ".vsc-vocab-master",
    ".celebrate-button",
  ].join(",");

  let audioCtx = null;
  let unlocked = false;
  let muted = readMuted();

  function readMuted() {
    try {
      return localStorage.getItem(MUTE_KEY) === "true";
    } catch (_) {
      return false;
    }
  }

  function persistMuted(value) {
    try {
      localStorage.setItem(MUTE_KEY, value ? "true" : "false");
    } catch (_) {
      /* ignore */
    }
  }

  function getContext() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioCtx;
  }

  // iOS Safari等の自動再生制限を解除するため、初回のユーザー操作時に呼ぶ
  function unlock() {
    if (unlocked && audioCtx && audioCtx.state !== "suspended") return;
    try {
      const ctx = getContext();
      if (ctx.state === "suspended") ctx.resume();
      unlocked = true;
    } catch (_) {
      /* AudioContext 非対応環境では黙ってスキップ */
    }
  }

  // 単音を鳴らす基本関数
  function playTone({ freq, duration = 0.15, type = "sine", volume = 0.2, delay = 0 }) {
    if (muted || !unlocked) return;
    let ctx;
    try {
      ctx = getContext();
    } catch (_) {
      return;
    }
    if (ctx.state === "suspended") ctx.resume();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0, ctx.currentTime + delay);
    gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + delay + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime + delay);
    osc.stop(ctx.currentTime + delay + duration);
  }

  function bindUnlock() {
    const once = { once: true, capture: true };
    document.addEventListener("click", unlock, once);
    document.addEventListener("touchstart", unlock, { ...once, passive: true });
    document.addEventListener("pointerdown", unlock, { ...once, passive: true });
  }

  function bindTapSounds() {
    document.addEventListener(
      "pointerdown",
      (event) => {
        if (event.button != null && event.button !== 0) return;
        const target = event.target && event.target.closest ? event.target.closest(TAP_SELECTOR) : null;
        if (!target || target.disabled || target.getAttribute("aria-disabled") === "true") return;
        api.tap();
      },
      { capture: true, passive: true }
    );
  }

  function bindMuteToggle() {
    const sfxToggle = document.getElementById("sfx-toggle");
    if (!sfxToggle) return;
    sfxToggle.checked = !muted;
    sfxToggle.addEventListener("change", (e) => {
      api.setMuted(!e.target.checked);
      if (!muted) {
        unlock();
        api.tap();
      }
    });
  }

  const api = {
    unlock,

    setMuted(value) {
      muted = Boolean(value);
      persistMuted(muted);
    },
    isMuted() {
      return muted;
    },

    // 正解音：明るい2音上昇（ド→ソ的な進行）
    correct() {
      playTone({ freq: 523.25, duration: 0.12, type: "sine", volume: 0.18 });
      playTone({ freq: 783.99, duration: 0.18, type: "sine", volume: 0.18, delay: 0.09 });
    },

    // 不正解音：柔らかい低音1音（責める印象を避けるため短く控えめに）
    incorrect() {
      playTone({ freq: 220, duration: 0.18, type: "sine", volume: 0.12 });
    },

    // ボタンタップ音：ごく短いクリック
    tap() {
      playTone({ freq: 600, duration: 0.04, type: "square", volume: 0.06 });
    },

    // コイン獲得音：キラッとした高音の2音
    coin() {
      playTone({ freq: 987.77, duration: 0.08, type: "triangle", volume: 0.15 });
      playTone({ freq: 1318.51, duration: 0.14, type: "triangle", volume: 0.15, delay: 0.06 });
    },

    // ストリーク更新音：3音の華やかな上昇（ド・ミ・ソ）
    streakUpdate() {
      playTone({ freq: 523.25, duration: 0.15, type: "sine", volume: 0.2 });
      playTone({ freq: 659.25, duration: 0.15, type: "sine", volume: 0.2, delay: 0.1 });
      playTone({ freq: 783.99, duration: 0.3, type: "sine", volume: 0.22, delay: 0.2 });
    },

    // Guardián発動音：落ち着いた鐘のような低め2音
    guardian() {
      playTone({ freq: 392, duration: 0.3, type: "sine", volume: 0.15 });
      playTone({ freq: 587.33, duration: 0.4, type: "sine", volume: 0.12, delay: 0.15 });
    },
  };

  bindUnlock();
  bindTapSounds();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindMuteToggle);
  } else {
    bindMuteToggle();
  }

  return api;
})();

window.SoundFX = SoundFX;
