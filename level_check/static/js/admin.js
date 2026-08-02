(() => {
  const RUBRIC_AXES = window.LEVEL_CHECK_RUBRIC_AXES || [
    "fluency",
    "pronunciation",
    "accuracy",
    "vocabulary",
    "response_latency",
  ];

  const statusMessage = document.getElementById("status-message");

  let settingsCache = null;
  let questionsCache = null;
  let currentQuestionTaskTab = "repeat";

  const TASK_FIELD = {
    repeat: { key: "text", label: "お題文" },
    sentence_build: { key: "target_sentence", label: "正解文" },
    qa: { key: "question", label: "質問文" },
  };

  function showStatus(message, isError) {
    statusMessage.textContent = message;
    statusMessage.classList.toggle("text-emerald-700", !isError);
    statusMessage.classList.toggle("text-rose-600", Boolean(isError));
    if (message) setTimeout(() => { statusMessage.textContent = ""; }, 4000);
  }

  async function apiFetch(path, options = {}) {
    const url = new URL(path, window.location.origin);
    const opts = { ...options };
    if (opts.body && !(opts.body instanceof FormData)) {
      opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    }
    const res = await fetch(url.toString(), opts);
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || "リクエストに失敗しました。");
    return data;
  }

  async function loadAll() {
    await Promise.all([loadSettings(), loadRoster(), loadQuestions(), loadSubmissions()]);
  }
  loadAll();

  // ── タブ切り替え ────────────────────────────────────────
  document.querySelectorAll("#admin-tabs .admin-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#admin-tabs .admin-tab-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const tab = btn.dataset.tab;
      document.querySelectorAll(".admin-tab-panel").forEach((panel) => {
        panel.classList.toggle("hidden", panel.dataset.tabPanel !== tab);
      });
    });
  });

  document.querySelectorAll("#question-task-tabs .admin-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#question-task-tabs .admin-tab-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      currentQuestionTaskTab = btn.dataset.taskTab;
      renderQuestions();
    });
  });

  // ── 設定 ────────────────────────────────────────────────
  async function loadSettings() {
    const data = await apiFetch("/level_check/admin/api/settings");
    settingsCache = data;
    renderSettings();
  }

  function renderSettings() {
    if (!settingsCache) return;

    const modelPicker = document.getElementById("ai-model-picker");
    modelPicker.innerHTML = "";
    settingsCache.ai_model_modes.forEach((mode) => {
      const label = document.createElement("label");
      label.className = "lc-mode-option";
      label.innerHTML = `<input type="radio" name="ai_model_mode" value="${mode.id}" ${mode.id === settingsCache.ai_model_mode ? "checked" : ""}>${mode.label}`;
      modelPicker.appendChild(label);
    });

    const infoPicker = document.getElementById("info-level-picker");
    infoPicker.innerHTML = "";
    settingsCache.info_levels.forEach((lvl) => {
      const label = document.createElement("label");
      label.className = "lc-mode-option";
      label.innerHTML = `<input type="radio" name="student_info_level" value="${lvl.id}" ${lvl.id === settingsCache.student_info_level ? "checked" : ""}>${lvl.label}`;
      infoPicker.appendChild(label);
    });

    document.getElementById("questions-per-task").value = settingsCache.questions_per_task;

    const weightsContainer = document.getElementById("rubric-weights");
    weightsContainer.innerHTML = "";
    RUBRIC_AXES.forEach((axis) => {
      const defaults = settingsCache.rubric_defaults[axis] || {};
      const weightPct = Math.round((settingsCache.rubric_weights[axis] || 0) * 100);
      const row = document.createElement("div");
      row.className = "rubric-weight-row";
      row.innerHTML = `
        <span class="rubric-weight-label">${defaults.label || axis}</span>
        <input type="range" min="0" max="100" value="${weightPct}" class="rubric-weight-slider" data-axis="${axis}">
        <span class="rubric-weight-value" data-axis-value="${axis}">${weightPct}%</span>
      `;
      weightsContainer.appendChild(row);
    });
    weightsContainer.querySelectorAll(".rubric-weight-slider").forEach((slider) => {
      slider.addEventListener("input", () => {
        const valueEl = weightsContainer.querySelector(`[data-axis-value="${slider.dataset.axis}"]`);
        if (valueEl) valueEl.textContent = `${slider.value}%`;
      });
    });
  }

  document.getElementById("save-settings-btn")?.addEventListener("click", async () => {
    const infoLevel = document.querySelector('input[name="student_info_level"]:checked')?.value;
    const questionsPerTask = document.getElementById("questions-per-task").value;
    const rubricWeights = {};
    document.querySelectorAll("#rubric-weights .rubric-weight-slider").forEach((slider) => {
      rubricWeights[slider.dataset.axis] = Number(slider.value) / 100;
    });

    try {
      await apiFetch("/level_check/admin/api/settings", {
        method: "POST",
        body: JSON.stringify({
          student_info_level: infoLevel,
          questions_per_task: questionsPerTask,
          rubric_weights: rubricWeights,
        }),
      });
      showStatus("設定を保存しました。");
      await loadSettings();
    } catch (err) {
      showStatus(err.message, true);
    }
  });

  // ── 管理設定（AIモデル選択のみパスワード必須） ──────────────
  document.getElementById("change-model-btn")?.addEventListener("click", async () => {
    const modelMode = document.querySelector('input[name="ai_model_mode"]:checked')?.value;
    const pwInput = document.getElementById("model-admin-password");
    const statusEl = document.getElementById("model-change-status");
    const password = pwInput?.value.trim() || "";

    try {
      await apiFetch("/level_check/admin/api/settings", {
        method: "POST",
        body: JSON.stringify({ ai_model_mode: modelMode, admin_password: password }),
      });
      if (statusEl) {
        statusEl.textContent = "AIモデルを変更しました。";
        statusEl.classList.remove("text-rose-600");
        statusEl.classList.add("text-emerald-700");
      }
      if (pwInput) pwInput.value = "";
      await loadSettings();
    } catch (err) {
      if (statusEl) {
        statusEl.textContent = err.message;
        statusEl.classList.remove("text-emerald-700");
        statusEl.classList.add("text-rose-600");
      }
    }
  });

  // ── 名簿 ────────────────────────────────────────────────
  async function loadRoster() {
    const data = await apiFetch("/level_check/admin/api/students");
    renderRoster(data.students || []);
  }

  function renderRoster(students) {
    const list = document.getElementById("roster-list");
    list.innerHTML = "";
    if (!students.length) {
      list.innerHTML = '<p class="text-sm text-slate-400">名簿が登録されていません。</p>';
      return;
    }
    students.forEach((student) => {
      const row = document.createElement("div");
      row.className = "roster-row flex items-center gap-2 flex-wrap";
      row.innerHTML = `
        <input class="lc-input w-24" data-field="class_name" value="${student.class_name}" placeholder="クラス">
        <input class="lc-input w-16" data-field="number" value="${student.number}" placeholder="番号">
        <input class="lc-input flex-1 min-w-[8rem]" data-field="name" value="${student.name}" placeholder="氏名">
        <button type="button" class="text-xs px-2.5 py-1 rounded-full border border-rose-200 text-rose-600 hover:bg-rose-50">削除</button>
      `;
      const inputs = row.querySelectorAll("input");
      const saveStudent = async () => {
        const updated = { id: student.id };
        inputs.forEach((input) => { updated[input.dataset.field] = input.value; });
        try {
          await apiFetch("/level_check/admin/api/students", {
            method: "POST",
            body: JSON.stringify({ student: updated }),
          });
          showStatus("名簿を保存しました。");
        } catch (err) {
          showStatus(err.message, true);
        }
      };
      inputs.forEach((input) => input.addEventListener("blur", saveStudent));
      row.querySelector("button").addEventListener("click", async () => {
        try {
          await apiFetch(`/level_check/admin/api/students/${student.id}`, { method: "DELETE" });
          await loadRoster();
        } catch (err) {
          showStatus(err.message, true);
        }
      });
      list.appendChild(row);
    });
  }

  document.getElementById("roster-add-btn")?.addEventListener("click", async () => {
    try {
      await apiFetch("/level_check/admin/api/students", {
        method: "POST",
        body: JSON.stringify({ student: { class_name: "", number: "", name: "" } }),
      });
      await loadRoster();
    } catch (err) {
      showStatus(err.message, true);
    }
  });

  document.getElementById("roster-upload-btn")?.addEventListener("click", async () => {
    const fileInput = document.getElementById("roster-file-input");
    const file = fileInput.files[0];
    if (!file) {
      showStatus("ファイルを選択してください。", true);
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    try {
      const data = await apiFetch("/level_check/admin/api/students/upload", { method: "POST", body: formData });
      showStatus(`${data.count}件の名簿を読み込みました。`);
      fileInput.value = "";
      await loadRoster();
    } catch (err) {
      showStatus(err.message, true);
    }
  });

  // ── 問題バンク ──────────────────────────────────────────
  async function loadQuestions() {
    const data = await apiFetch("/level_check/admin/api/questions");
    questionsCache = data.questions;
    renderQuestions();
  }

  function renderQuestions() {
    const list = document.getElementById("questions-list");
    list.innerHTML = "";
    if (!questionsCache) return;

    const items = questionsCache[currentQuestionTaskTab] || [];
    const fieldInfo = TASK_FIELD[currentQuestionTaskTab];

    if (!items.length) {
      list.innerHTML = '<p class="text-sm text-slate-400">問題が登録されていません。「AIで追加生成」または「手動で追加」してください。</p>';
      return;
    }

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "question-row flex items-center gap-2 flex-wrap";
      const extraField = currentQuestionTaskTab === "qa"
        ? `<input class="lc-input w-20" data-field="time_limit_sec" type="number" min="5" max="60" value="${item.time_limit_sec || 15}" title="制限時間(秒)">`
        : "";
      row.innerHTML = `
        <input class="lc-input flex-1 min-w-[12rem]" data-field="${fieldInfo.key}" value="${(item[fieldInfo.key] || "").replace(/"/g, "&quot;")}" placeholder="${fieldInfo.label}">
        <input class="lc-input w-16" data-field="level" value="${item.level || ""}" placeholder="レベル">
        ${extraField}
        <label class="text-xs flex items-center gap-1"><input type="checkbox" data-field="active" ${item.active ? "checked" : ""}>表示</label>
        <button type="button" class="text-xs px-2.5 py-1 rounded-full border border-rose-200 text-rose-600 hover:bg-rose-50">削除</button>
      `;

      const saveItem = async () => {
        const updates = {};
        row.querySelectorAll("[data-field]").forEach((input) => {
          if (input.type === "checkbox") updates[input.dataset.field] = input.checked;
          else updates[input.dataset.field] = input.value;
        });
        try {
          const data = await apiFetch(`/level_check/admin/api/questions/${currentQuestionTaskTab}/${item.id}`, {
            method: "POST",
            body: JSON.stringify({ item: updates }),
          });
          questionsCache = data.questions;
          showStatus("問題を保存しました。");
        } catch (err) {
          showStatus(err.message, true);
        }
      };
      row.querySelectorAll("input").forEach((input) => {
        input.addEventListener(input.type === "checkbox" ? "change" : "blur", saveItem);
      });
      row.querySelector("button").addEventListener("click", async () => {
        try {
          const data = await apiFetch(`/level_check/admin/api/questions/${currentQuestionTaskTab}/${item.id}`, {
            method: "DELETE",
          });
          questionsCache = data.questions;
          renderQuestions();
        } catch (err) {
          showStatus(err.message, true);
        }
      });
      list.appendChild(row);
    });
  }

  document.getElementById("question-add-btn")?.addEventListener("click", async () => {
    const fieldInfo = TASK_FIELD[currentQuestionTaskTab];
    const item = { [fieldInfo.key]: "", level: "A2" };
    try {
      const data = await apiFetch(`/level_check/admin/api/questions/${currentQuestionTaskTab}`, {
        method: "POST",
        body: JSON.stringify({ item }),
      });
      questionsCache = data.questions;
      renderQuestions();
    } catch (err) {
      showStatus(err.message, true);
    }
  });

  document.getElementById("generate-questions-btn")?.addEventListener("click", async () => {
    const count = document.getElementById("generate-count").value || 5;
    const statusEl = document.getElementById("generate-status");
    statusEl.textContent = "生成中...";
    try {
      const data = await apiFetch(`/level_check/admin/api/questions/${currentQuestionTaskTab}/generate`, {
        method: "POST",
        body: JSON.stringify({ count }),
      });
      questionsCache = data.questions;
      renderQuestions();
      statusEl.textContent = `${data.generated_count}件を生成しました。`;
    } catch (err) {
      statusEl.textContent = "";
      showStatus(err.message, true);
    }
  });

  // ── 受験結果 ────────────────────────────────────────────
  async function loadSubmissions() {
    const data = await apiFetch("/level_check/admin/api/submissions");
    renderSubmissions(data.submissions || []);
    document.getElementById("export-submissions-link").href = "/level_check/admin/api/submissions/export";
  }

  function renderSubmissions(submissions) {
    const list = document.getElementById("submissions-list");
    list.innerHTML = "";
    if (!submissions.length) {
      list.innerHTML = '<p class="text-sm text-slate-400">受験結果はまだありません。</p>';
      return;
    }
    submissions.forEach((s) => {
      const info = s.student_info || {};
      const overall = s.overall || {};
      const row = document.createElement("div");
      row.className = "submission-row flex items-center justify-between gap-2 flex-wrap";
      const infoText = [info.class_name, info.number, info.name].filter(Boolean).join(" / ") || "（情報なし）";
      row.innerHTML = `
        <div>
          <p class="text-sm font-semibold text-slate-700">${infoText}</p>
          <p class="text-xs text-slate-400">${s.submitted_at || ""} ・ CEFR: <strong>${overall.cefr_band || "—"}</strong> (${overall.weighted_total ?? "—"})</p>
        </div>
        <button type="button" class="text-xs px-2.5 py-1 rounded-full border border-rose-200 text-rose-600 hover:bg-rose-50">削除</button>
      `;
      row.querySelector("button").addEventListener("click", async () => {
        try {
          await apiFetch(`/level_check/admin/api/submissions/${s.id}`, { method: "DELETE" });
          await loadSubmissions();
        } catch (err) {
          showStatus(err.message, true);
        }
      });
      list.appendChild(row);
    });
  }
})();
