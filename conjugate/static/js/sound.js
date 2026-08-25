/**
 * サウンドエフェクトモジュール（ElevenLabsで生成した音声ファイルを再生）
 */
const SoundFX = (() => {
  const MUTE_KEY = "sfx_muted";
  const SFX_BASE = "/static/audio/conjugate/";
  const SFX_VERSION = "20260825a";
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

  function makeAudio(name) {
    const audio = new Audio(`${SFX_BASE}${name}.mp3?v=${SFX_VERSION}`);
    audio.preload = "auto";
    audio.volume = 0.5;
    return audio;
  }

  const sounds = {
    correct: makeAudio("sfx-correct"),
    incorrect: makeAudio("sfx-incorrect"),
    tap: makeAudio("sfx-tap"),
    coin: makeAudio("sfx-coin"),
    streak: makeAudio("sfx-streak"),
    guardian: makeAudio("sfx-guardian"),
  };

  function play(key) {
    if (muted || !unlocked) return;
    const base = sounds[key];
    if (!base) return;
    const clone = base.cloneNode();
    clone.volume = base.volume;
    clone.play().catch(() => {
      /* 自動再生制限等でエラーになっても静かに無視する */
    });
  }

  // iOS Safari等の自動再生制限を解除するため、初回のユーザー操作時に呼ぶ
  function unlock() {
    if (unlocked) return;
    unlocked = true;
    Object.values(sounds).forEach((audio) => {
      const prev = audio.volume;
      audio.volume = 0;
      audio
        .play()
        .then(() => {
          audio.pause();
          audio.currentTime = 0;
          audio.volume = prev;
        })
        .catch(() => {
          audio.volume = prev;
        });
    });
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
    correct: () => play("correct"),
    incorrect: () => play("incorrect"),
    tap: () => play("tap"),
    coin: () => play("coin"),
    streakUpdate: () => play("streak"),
    guardian: () => play("guardian"),
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
