"use strict";

const UNLOCK_STORAGE_KEY = "debate_admin_unlocked";

const passwordInput = document.getElementById("admin-password");
const unlockBtn = document.getElementById("unlock-btn");
const lockMessage = document.getElementById("lock-message");
const settingsPanel = document.getElementById("settings-panel");
const statusMessage = document.getElementById("status-message");
const pageBgLayer = document.getElementById("page-bg-layer");
const bgPicker = document.getElementById("bg-picker");
const bgOpacitySlider = document.getElementById("bg-opacity-slider");
const bgOpacityValue = document.getElementById("bg-opacity-value");
const judgeModelPicker = document.getElementById("judge-model-picker");
const judgeModelCurrent = document.getElementById("judge-model-current");
const sessionsList = document.getElementById("sessions-list");
const sessionsCount = document.getElementById("sessions-count");
const sessionsRefreshBtn = document.getElementById("sessions-refresh-btn");
const transcriptionModePicker = document.getElementById("transcription-mode-picker");

let unlocked = false;
let saveTimer = null;
let currentBackgroundId = null;
let currentJudgeModelMode = "4o";

function getStoredPassword() {
  try {
    return sessionStorage.getItem(UNLOCK_STORAGE_KEY) || "";
  } catch (_) {
    return "";
  }
}

function saveUnlockState(password) {
  try {
    sessionStorage.setItem(UNLOCK_STORAGE_KEY, password);
  } catch (_) {}
}

function clearUnlockState() {
  try {
    sessionStorage.removeItem(UNLOCK_STORAGE_KEY);
  } catch (_) {}
}

function applyUnlockUI() {
  unlocked = true;
  passwordInput.disabled = true;
  unlockBtn.disabled = true;
  settingsPanel.classList.remove("hidden");
}

function showLockMessage(msg) {
  lockMessage.textContent = msg;
  lockMessage.classList.remove("hidden");
}

function hideLockMessage() {
  lockMessage.classList.add("hidden");
}

function applyBackgroundOpacity(opacity) {
  const value = Math.max(0, Math.min(1, Number(opacity) || 0));
  if (pageBgLayer) pageBgLayer.style.opacity = String(value);
  const percent = Math.round(value * 100);
  if (bgOpacitySlider) bgOpacitySlider.value = String(percent);
  if (bgOpacityValue) bgOpacityValue.textContent = String(percent);
}

function getBackgroundOpacityFromSlider() {
  const percent = parseInt(bgOpacitySlider?.value, 10);
  return Number.isFinite(percent) ? percent / 100 : 0.32;
}

function applyBackground(bgId, imageUrl) {
  currentBackgroundId = bgId;
  if (pageBgLayer && imageUrl) {
    pageBgLayer.style.backgroundImage = `url("${imageUrl}")`;
  }
  document.querySelectorAll(".bg-pick-btn").forEach((btn) => {
    btn.classList.toggle("bg-pick-btn-active", btn.dataset.bgId === bgId);
  });
}

function clampRatingLevel(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(5, Math.round(n)));
}

function renderJudgeModelRatingRow(label, level) {
  const filled = clampRatingLevel(level);
  const segments = Array.from({ length: 5 }, (_, index) => {
    const filledClass = index < filled ? " is-filled" : "";
    return `<span class="debate-mode-rating-seg${filledClass}"></span>`;
  }).join("");
  return `<span class="debate-mode-rating-row">
    <span class="debate-mode-rating-label">${label}</span>
    <span class="debate-mode-rating-bar" aria-label="${label} ${filled}/5">${segments}</span>
  </span>`;
}

function renderJudgeModelOptions(modes, selectedMode) {
  if (!judgeModelPicker || !Array.isArray(modes) || !modes.length) return;
  judgeModelPicker.innerHTML = modes
    .map((mode) => {
      const id = escapeHtml(mode.id || "");
      const title = escapeHtml(mode.model || mode.label || id);
      const checked = id === selectedMode ? " checked" : "";
      return `<label class="debate-mode-option debate-mode-option--compact">
        <input type="radio" name="judge_model_mode" value="${id}"${checked} />
        <span class="debate-mode-option-body">
          <span class="debate-mode-option-title">${title}</span>
          <span class="debate-mode-ratings">
            ${renderJudgeModelRatingRow("コスパ", mode.cost_performance)}
            ${renderJudgeModelRatingRow("性能", mode.performance)}
          </span>
        </span>
      </label>`;
    })
    .join("");
}

function applyJudgeModelMode(mode, activeModel) {
  currentJudgeModelMode = mode || "4o";
  if (judgeModelCurrent) {
    judgeModelCurrent.textContent = activeModel || "—";
  }
  judgeModelPicker?.querySelectorAll('input[name="judge_model_mode"]').forEach((input) => {
    input.checked = input.value === currentJudgeModelMode;
  });
}

function getSelectedJudgeModelMode() {
  const checked = judgeModelPicker?.querySelector('input[name="judge_model_mode"]:checked');
  return checked?.value || currentJudgeModelMode || "4o";
}

async function fetchSettings() {
  const res = await fetch("/debate/admin/api/settings");
  if (!res.ok) throw new Error("設定の取得に失敗しました");
  return res.json();
}

async function saveSettings(payload) {
  const res = await fetch("/debate/admin/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "保存に失敗しました");
  return data;
}

function getSelectedTranscriptionMode() {
  const checked = transcriptionModePicker?.querySelector('input[name="transcription_mode"]:checked');
  return checked?.value === "realtime" ? "realtime" : "batch";
}

function applyTranscriptionMode(mode) {
  const value = mode === "realtime" ? "realtime" : "batch";
  transcriptionModePicker?.querySelectorAll('input[name="transcription_mode"]').forEach((input) => {
    input.checked = input.value === value;
  });
}

function collectPayload() {
  return {
    admin_password: passwordInput.value.trim(),
    background_id: currentBackgroundId,
    background_opacity: getBackgroundOpacityFromSlider(),
    transcription_mode: getSelectedTranscriptionMode(),
    judge_model_mode: getSelectedJudgeModelMode(),
  };
}

async function loadSettingsIntoUI() {
  const data = await fetchSettings();
  const activeBtn = bgPicker?.querySelector(`.bg-pick-btn[data-bg-id="${data.background_id}"]`);
  applyBackground(data.background_id, activeBtn?.dataset.bgImage);
  applyBackgroundOpacity(data.background_opacity ?? 0.32);
  applyTranscriptionMode(data.transcription_mode ?? "batch");
  renderJudgeModelOptions(data.judge_model_modes || [], data.judge_model_mode || "4o");
  applyJudgeModelMode(data.judge_model_mode || "4o", data.judge_model);
}

function scheduleSave() {
  if (!unlocked) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      const saved = await saveSettings(collectPayload());
      const activeBtn = bgPicker?.querySelector(`.bg-pick-btn[data-bg-id="${saved.background_id}"]`);
      applyBackground(saved.background_id, activeBtn?.dataset.bgImage);
      applyBackgroundOpacity(saved.background_opacity ?? 0.32);
      applyTranscriptionMode(saved.transcription_mode ?? "batch");
      applyJudgeModelMode(saved.judge_model_mode || "4o", saved.judge_model);
      statusMessage.textContent = "保存しました";
    } catch (err) {
      statusMessage.textContent = "";
      showLockMessage(err.message);
    }
  }, 300);
}

// ── 保存済みセッション一覧（再開・削除） ─────────────────────
function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function splitDateTime(iso) {
  if (!iso) return { date: "—", time: "—" };
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return { date: iso, time: "" };
    return {
      date: d.toLocaleDateString("ja-JP", { year: "numeric", month: "2-digit", day: "2-digit" }),
      time: d.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    };
  } catch (_) {
    return { date: iso, time: "" };
  }
}

function renderSessions(sessions) {
  if (!sessionsList) return;
  if (sessionsCount) sessionsCount.textContent = `${sessions.length}件`;

  if (!sessions.length) {
    sessionsList.innerHTML = '<p class="text-sm text-slate-400">保存されたセッションはありません。</p>';
    return;
  }

  const rows = sessions
    .map((s) => {
      const dt = splitDateTime(s.updated_at || s.created_at);
      const done = s.confirmed_parts === s.total_parts && s.total_parts > 0;
      const progressLabel = done
        ? `<span class="text-emerald-600 font-semibold">完了</span>`
        : `<span>${s.confirmed_parts}/${s.total_parts} 確定</span>` +
          (s.in_progress_parts ? ` ・ <span class="text-amber-600">${s.in_progress_parts} 進行中</span>` : "");

      const judgeLabelMap = { batch: "モードA", realtime: "モードB", mixed: "混在" };
      let judgeLabel = "";
      if (s.judge_status === "done") {
        const modeLabel = judgeLabelMap[s.judge_transcription_mode] || "";
        const modelLabel = s.judge_model ? escapeHtml(s.judge_model) : "";
        judgeLabel =
          `<span class="text-indigo-600 font-semibold">判定: ${escapeHtml(s.judge_winner || "-")}勝利</span>` +
          (modelLabel ? ` <span class="text-slate-400">(${modelLabel})</span>` : "") +
          (modeLabel ? ` <span class="text-slate-400">[${modeLabel}]</span>` : "");
      } else if (s.judge_status === "judging") {
        judgeLabel = `<span class="text-amber-600">ジャッジ実行中…</span>`;
      } else if (s.judge_status === "error") {
        judgeLabel = `<span class="text-rose-600">ジャッジ失敗</span>`;
      }

      return `
        <div class="rounded-xl border border-slate-100 bg-white/70 px-4 py-3 hover:border-brand/30 transition-colors">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-slate-800">${escapeHtml(s.motion)}</p>
              <div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                <span><span class="font-semibold text-slate-400">日付</span> ${escapeHtml(dt.date)}</span>
                <span><span class="font-semibold text-slate-400">時刻</span> ${escapeHtml(dt.time)}</span>
                <span>${progressLabel}</span>
                ${judgeLabel ? `<span>${judgeLabel}</span>` : ""}
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <a href="/debate/session/${encodeURIComponent(s.session_id)}"
                class="text-xs px-3 py-1.5 rounded-full bg-brand/10 text-brand-dark font-semibold hover:bg-brand/20 transition-colors">
                再開
              </a>
              <button type="button" class="btn-delete-session text-xs px-3 py-1.5 rounded-full border border-rose-200 text-rose-600 hover:bg-rose-50 transition-colors"
                data-session-id="${escapeHtml(s.session_id)}">
                削除
              </button>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  sessionsList.innerHTML = rows;
}

async function loadSessions() {
  if (!sessionsList || !unlocked) return;
  const password = getStoredPassword() || passwordInput.value.trim();
  sessionsList.innerHTML = '<p class="text-sm text-slate-400">読み込み中...</p>';
  try {
    const res = await fetch(`/debate/admin/api/sessions?admin_password=${encodeURIComponent(password)}`);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "セッション一覧の取得に失敗しました");
    renderSessions(data.sessions || []);
  } catch (err) {
    sessionsList.innerHTML = `<p class="text-sm text-rose-600">${escapeHtml(err.message)}</p>`;
  }
}

sessionsRefreshBtn?.addEventListener("click", loadSessions);

sessionsList?.addEventListener("click", async (e) => {
  const btn = e.target.closest(".btn-delete-session");
  if (!btn || !unlocked) return;

  const sessionId = btn.dataset.sessionId;
  if (!window.confirm("このセッションの録音・文字起こしデータを完全に削除します。よろしいですか？")) return;

  btn.disabled = true;
  btn.textContent = "削除中...";
  try {
    const password = getStoredPassword() || passwordInput.value.trim();
    const res = await fetch(`/debate/admin/api/sessions/${encodeURIComponent(sessionId)}/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ admin_password: password }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "削除に失敗しました");
    statusMessage.textContent = "セッションを削除しました";
    await loadSessions();
  } catch (err) {
    statusMessage.textContent = "";
    showLockMessage(err.message);
    btn.disabled = false;
    btn.textContent = "削除";
  }
});

async function tryUnlock() {
  hideLockMessage();
  const password = passwordInput.value.trim();
  if (!password) {
    showLockMessage("パスワードを入力してください");
    return;
  }

  try {
    const res = await fetch("/debate/admin/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ admin_password: password }),
    });
    const data = await res.json();
    if (res.status === 403) {
      showLockMessage("パスワードが違います");
      return;
    }
    if (!res.ok) throw new Error(data.error || "解除に失敗しました");

    saveUnlockState(password);
    applyUnlockUI();
    await loadSettingsIntoUI();
    await loadSessions();
    statusMessage.textContent = "管理設定を解除しました";
  } catch (err) {
    showLockMessage(err.message);
  }
}

async function restoreUnlockFromStorage() {
  const password = getStoredPassword();
  if (!password) return;

  passwordInput.value = password;
  hideLockMessage();

  try {
    const res = await fetch("/debate/admin/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ admin_password: password }),
    });
    const data = await res.json();
    if (res.status === 403) {
      clearUnlockState();
      passwordInput.value = "";
      return;
    }
    if (!res.ok) return;

    applyUnlockUI();
    await loadSettingsIntoUI();
    await loadSessions();
  } catch (_) {
    // 保存済み解除の復元に失敗した場合はロック画面のまま
  }
}

unlockBtn?.addEventListener("click", tryUnlock);
passwordInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") tryUnlock();
});

bgPicker?.addEventListener("click", (e) => {
  const btn = e.target.closest(".bg-pick-btn");
  if (!btn || !unlocked) return;
  applyBackground(btn.dataset.bgId, btn.dataset.bgImage);
  scheduleSave();
});

judgeModelPicker?.addEventListener("change", () => {
  if (!unlocked) return;
  scheduleSave();
});

bgOpacitySlider?.addEventListener("input", () => {
  if (!unlocked) return;
  applyBackgroundOpacity(getBackgroundOpacityFromSlider());
  scheduleSave();
});

transcriptionModePicker?.addEventListener("change", () => {
  if (!unlocked) return;
  scheduleSave();
});

restoreUnlockFromStorage();
