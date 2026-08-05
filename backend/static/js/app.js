/* 试卷分析系统 - 前端逻辑 v0.2 */
"use strict";

const $ = (sel) => document.querySelector(sel);

let SECTIONS = [];
let QTYPES = [];
let OUTLINE = [];           // 高考物理知识大纲（知识点+说明）
let indFiles = [];          // 个人分析上传的试卷文件
let indQuestions = [];      // 个人分析题目配置
let batFile = null;         // 批量 xlsx 文件信息
let batPaper = null;        // 批量试卷文件信息
let batQuestions = [];      // 批量题目配置
let batPaperQuestions = []; // 批量试卷提取出的题目（含原文）
let indPaperQuestions = []; // 个人试卷提取出的题目（含原文）
let catVideos = [];         // 当前班型视频目录
let lastResult = {};        // 最近生成的报告
let lastJobId = null;       // 批量任务 ID

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isError ? " error" : "");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), 3200);
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function sectionOptions(selected) {
  return SECTIONS.map((s) => `<option value="${s.key}" ${s.key === selected ? "selected" : ""}>${s.name}</option>`).join("");
}
function typeOptions(selected) {
  return QTYPES.map((t) => `<option value="${t.key}" ${t.key === selected ? "selected" : ""}>${t.name}</option>`).join("");
}

/* 知识点下拉：按大纲板块分组，说明放 title */
function kpOptions(selected) {
  let html = '<option value="">-- 请选择知识点 --</option>';
  for (const sec of OUTLINE) {
    html += `<optgroup label="${esc(sec.name)}">`;
    for (const kp of sec.knowledge_points) {
      html += `<option value="${esc(kp.name)}" data-sec="${esc(sec.key)}" data-desc="${esc(kp.desc || "")}" ${kp.name === selected ? "selected" : ""}>${esc(kp.name)}</option>`;
    }
    html += "</optgroup>";
  }
  return html;
}

/* ---------- 标签页切换 ---------- */
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "catalog") loadCatalog();
    if (btn.dataset.tab === "history") loadHistory();
  });
});

/* ---------- 初始化 ---------- */
async function init() {
  try {
    const kb = await api("/api/sections");
    SECTIONS = kb.sections;
    QTYPES = kb.question_types;
  } catch (e) { toast("初始化失败: " + e.message, true); }
  await loadOutline();
  try {
    const s = await api("/api/settings");
    $("#set-mode").value = s.engine_mode;
    $("#set-school").value = s.school_name || "";
    $("#set-partial").value = String(s.multi_choice_partial);
    $("#set-key").value = s.llm_api_key || "";
    $("#set-url").value = s.llm_base_url || "";
    $("#set-model").value = s.llm_model || "";
    $("#cat-ocr-tip").textContent = s.ocr_available
      ? "OCR 组件可用：上传目录截图后自动识别视频标题。"
      : "提示：OCR 组件未安装（pip install rapidocr-onnxruntime），目前只能手动录入视频标题。";
  } catch (e) {}
}
async function loadOutline() {
  try {
    const o = await api("/api/outline");
    OUTLINE = o.sections || [];
    renderIndQuestions();
    renderBatQuestions();
  } catch (e) { toast("大纲加载失败: " + e.message, true); }
}
init();

/* ================= 个人分析 ================= */
$("#ind-paper").addEventListener("change", async (e) => {
  const files = [...e.target.files];
  e.target.value = "";
  for (const f of files) {
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await api("/api/upload", { method: "POST", body: fd });
      indFiles.push(r);
    } catch (err) { toast(err.message, true); }
  }
  renderIndFiles();
});

function renderIndFiles() {
  $("#ind-files").innerHTML = indFiles.map((f) => `
    <div class="file-chip">
      ${f.ext.match(/\.(png|jpe?g|webp|bmp)$/i) ? `<img src="${f.url}">` : `<span>📄</span>`}
      <span title="${esc(f.original)}">${esc(f.original)}</span>
      <span class="x" onclick="removeIndFile('${f.filename}')">×</span>
    </div>`).join("");
}
window.removeIndFile = (name) => {
  indFiles = indFiles.filter((f) => f.filename !== name);
  renderIndFiles();
};

function renderIndQuestions() {
  const tb = $("#ind-qtbl tbody");
  tb.innerHTML = indQuestions.map((q, i) => `
    <tr data-i="${i}">
      <td><input value="${esc(q.qid)}" oninput="updQ('ind',${i},'qid',this.value)"></td>
      <td><select onchange="updQ('ind',${i},'qtype',this)">${typeOptions(q.qtype)}</select></td>
      <td>
        <select data-i="${i}" onchange="updQ('ind',${i},'kp',this)">${kpOptions(q.knowledge_point)}</select>
        <div class="kp-desc" id="ind-kp-desc-${i}">${esc(kpDesc(q.knowledge_point))}</div>
      </td>
      <td><input type="number" step="0.5" min="0" value="${q.full_score}" oninput="updQ('ind',${i},'full_score',this.value)"></td>
      <td><input type="number" step="0.5" min="0" value="${q.got_score}" oninput="updQ('ind',${i},'got_score',this.value)"></td>
      <td><button class="del-btn" onclick="delQ('ind',${i})">✕</button></td>
    </tr>`).join("");
}
function kpDesc(name) {
  if (!name) return "";
  for (const sec of OUTLINE) {
    const kp = sec.knowledge_points.find((k) => k.name === name);
    if (kp) return kp.desc || "";
  }
  return "";
}
window.updQ = (mode, i, field, el) => {
  const arr = mode === "ind" ? indQuestions : batQuestions;
  // 兼容两种传参：oninput 传 this.value（字符串），onchange 传 this（元素）
  const val = (el && typeof el === "object" && "value" in el) ? el.value : el;
  if (field === "kp") {
    const opt = el.selectedOptions[0];
    arr[i].knowledge_point = el.value;
    arr[i].section_key = (opt && opt.dataset.sec) || "lixue";
    const descEl = document.getElementById(`${mode}-kp-desc-${i}`);
    if (descEl) descEl.textContent = (opt && opt.dataset.desc) || "";
    if (mode === "bat") renderBatQuestions(); else renderIndQuestions();
  } else if (field === "qtype") {
    arr[i].qtype = el.value;
  } else {
    arr[i][field] = val;
  }
  // 注意：不再因分值/得分输入而整体重绘表格，避免输入框失焦、连打丢值
};
window.delQ = (mode, i) => {
  if (mode === "ind") { indQuestions.splice(i, 1); renderIndQuestions(); }
  else { batQuestions.splice(i, 1); renderBatQuestions(); }
};

$("#ind-add-q").addEventListener("click", () => {
  indQuestions.push({ qid: String(indQuestions.length + 1), qtype: "single", section_key: "lixue", full_score: 4, got_score: 0, knowledge_point: "" });
  renderIndQuestions();
});

$("#ind-extract").addEventListener("click", async () => {
  const pdf = indFiles.find((f) => f.ext === ".pdf" || f.ext === ".docx" || f.ext === ".doc" || f.ext === ".txt");
  if (!pdf) return toast("请先上传 PDF/Word 试卷文件", true);
  try {
    const fd = new FormData();
    fd.append("file", await (await fetch(pdf.url)).blob(), pdf.original);
    const r = await api("/api/paper/text", { method: "POST", body: fd });
    if (!r.questions.length) return toast("未能从试卷中识别出题目，请手动添加", true);
    indPaperQuestions = r.questions;
    indQuestions = r.questions.map((q) => ({
      qid: q.qid, qtype: "single", section_key: "lixue",
      full_score: q.score ?? 4, got_score: q.score ?? 0, knowledge_point: "",
    }));
    toast(`已提取 ${indQuestions.length} 道题，自动匹配知识点中…`);
    renderIndQuestions();
    await suggestKnowledge("ind");   // 自动匹配题型/板块/知识点
  } catch (err) { toast("提取失败: " + err.message, true); }
});

$("#ind-run").addEventListener("click", async () => {
  const payload = {
    teacher: $("#ind-teacher").value.trim(),
    student: $("#ind-student").value.trim(),
    class_type: $("#ind-class").value,
    mode: $("#ind-mode").value,
    questions: indQuestions.map((q) => ({ ...q, full_score: parseFloat(q.full_score) || 0, got_score: parseFloat(q.got_score) || 0 })),
  };
  if (!payload.student) return toast("请填写学生姓名", true);
  if (!payload.questions.length) return toast("请至少配置一道题", true);
  const emptyKp = payload.questions.filter((q) => !q.knowledge_point);
  if (emptyKp.length) return toast(`还有 ${emptyKp.length} 道题未选择考察知识点（必填）`, true);
  try {
    const r = await api("/api/analyze/individual", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    lastResult = r;
    $("#ind-score").innerHTML = `
      <div class="score-card"><div class="v">${r.score} / ${r.full}</div><div class="k">总得分</div></div>
      <div class="score-card"><div class="v">${(r.rate * 100).toFixed(0)}%</div><div class="k">得分率</div></div>
      <div class="score-card"><div class="v">${esc(r.difficulty)}</div><div class="k">整体难度</div></div>`;
    $("#ind-preview").src = r.html_url;
    $("#ind-result").classList.remove("hidden");
    toast("报告生成成功");
  } catch (err) { toast(err.message, true); }
});
$("#ind-pdf").addEventListener("click", () => window.open(lastResult.pdf_url));
$("#ind-img").addEventListener("click", () => window.open(lastResult.image_url));
$("#ind-open").addEventListener("click", () => window.open(lastResult.html_url));

/* 智能标注知识点：优先大模型 API（后端自动判断），本地规则兜底。
   分批调用展示进度（已分析 X/N 题），5 分钟无结果提示超时。 */
async function suggestKnowledge(mode) {
  const arr = mode === "ind" ? indQuestions : batQuestions;
  const paperQs = mode === "ind" ? indPaperQuestions : batPaperQuestions;
  if (!paperQs.length) return toast("请先上传试卷并点击「从试卷提取题目」", true);
  const textByQid = {};
  for (const pq of paperQs) textByQid[String(pq.qid)] = pq.text || "";
  const targets = arr.filter((q) => !q.knowledge_point);   // 只标注未选的
  const items = targets.map((q) => ({ qid: q.qid, text: textByQid[String(q.qid)] || "" }));
  if (!items.length) return toast("所有题目都已标注知识点", false);

  const BATCH = 5, TIMEOUT_MS = 300000;  // 每批 5 题，总超时 5 分钟
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let done = 0, total = items.length, applied = 0;
  toast(`正在智能标注（大模型优先）… 0/${total}`);
  try {
    for (let i = 0; i < items.length; i += BATCH) {
      const batch = items.slice(i, i + BATCH);
      const r = await api("/api/suggest/knowledge", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions: batch }),
        signal: controller.signal,
      });
      for (const sug of r.suggestions) {
        const q = arr.find((x) => String(x.qid) === String(sug.qid));
        if (q && !q.knowledge_point) {
          q.section_key = sug.section_key;
          q.knowledge_point = sug.knowledge_point;
          applied++;
        }
      }
      done += batch.length;
      toast(`正在智能标注（${r.engine === "llm" ? "大模型" : "本地规则"}）… ${Math.min(done, total)}/${total}`);
    }
    if (mode === "ind") renderIndQuestions(); else renderBatQuestions();
    const empty = arr.filter((q) => !q.knowledge_point).length;
    toast(`标注完成：新增 ${applied} 道，剩余 ${empty} 道需手动选择`);
  } catch (err) {
    toast("智能标注超时（5 分钟），请手动添加知识点", true);
    if (mode === "ind") renderIndQuestions(); else renderBatQuestions();
  } finally {
    clearTimeout(timer);
  }
}
$("#ind-suggest").addEventListener("click", () => suggestKnowledge("ind"));
$("#bat-suggest").addEventListener("click", () => suggestKnowledge("bat"));

/* ================= 批量分析 ================= */
$("#bat-xlsx").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  try {
    const r = await api("/api/batch/preview", { method: "POST", body: fd });
    batFile = r;
    $("#bat-info").textContent = `已解析：${r.student_count} 名学生，${r.question_ids.length} 道题，老师：${r.teachers.join("、") || "无（未识别到老师列）"}`;
    $("#bat-teacher").innerHTML = `<option value="">-- 请选择老师 --</option>` + r.teachers.map((t) => `<option>${esc(t)}</option>`).join("");
    batQuestions = (r.question_meta || []).map((m) => ({
      qid: m.qid,
      qtype: m.qtype || "single",
      section_key: "lixue",
      full_score: m.default_score || "",
      knowledge_point: "",
    }));
    toast(`已自动识别 ${batQuestions.length} 道题，请补充考察知识点`);
    renderBatQuestions();
  } catch (err) { toast("解析失败: " + err.message, true); }
});

$("#bat-paper").addEventListener("change", (e) => {
  batPaper = e.target.files[0] ? { name: e.target.files[0].name } : null;
});

$("#bat-extract").addEventListener("click", async () => {
  const f = $("#bat-paper").files[0];
  if (!f) return toast("请先选择试卷文件", true);
  const fd = new FormData();
  fd.append("file", f);
  try {
    const r = await api("/api/paper/text", { method: "POST", body: fd });
    if (!r.questions.length) return toast("未能识别题目，请手动添加", true);
    batPaperQuestions = r.questions;
    const existing = new Map(batQuestions.map((q) => [q.qid, q]));
    for (const pq of r.questions) {
      const cur = existing.get(pq.qid);
      if (cur) {
        if (!cur.full_score && pq.score) cur.full_score = pq.score;
      } else {
        existing.set(pq.qid, { qid: pq.qid, qtype: "calculation", section_key: "lixue", full_score: pq.score ?? "", knowledge_point: "" });
      }
    }
    batQuestions = [...existing.values()];
    // 大题分值均分到小题：15=12分 → 15(1)/15(2)/15(3) 各4分
    const byParent = {};
    for (const q of batQuestions) {
      const mm = String(q.qid).match(/^(\d{1,3})\((\d{1,2})\)$/);
      if (mm) (byParent[mm[1]] = byParent[mm[1]] || []).push(q);
    }
    for (const [pid, parts] of Object.entries(byParent)) {
      if (parts.length < 2) continue;
      const parent = batQuestions.find((q) => String(q.qid) === pid);
      if (!parent || !parent.full_score) continue;
      const missing = parts.filter((p) => !p.full_score);
      if (!missing.length) continue;
      const total = parseFloat(parent.full_score);
      const share = Math.round((total / parts.length) * 10) / 10;
      let assigned = 0;
      parts.forEach((p, i) => {
        if (!p.full_score) {
          p.full_score = i === parts.length - 1 ? Math.round((total - assigned) * 10) / 10 : share;
          assigned += parseFloat(p.full_score);
        }
      });
      batQuestions = batQuestions.filter((q) => String(q.qid) !== pid);
    }
    toast(`已合并试卷信息，共 ${batQuestions.length} 道题，自动匹配知识点中…`);
    renderBatQuestions();
    await suggestKnowledge("bat");
  } catch (err) { toast("提取失败: " + err.message, true); }
});

function renderBatQuestions() {
  const tb = $("#bat-qtbl tbody");
  tb.innerHTML = batQuestions.map((q, i) => `
    <tr data-i="${i}">
      <td><input value="${esc(q.qid)}" oninput="updQ('bat',${i},'qid',this.value)"></td>
      <td><select onchange="updQ('bat',${i},'qtype',this)">${typeOptions(q.qtype)}</select></td>
      <td>
        <select data-i="${i}" onchange="updQ('bat',${i},'kp',this)">${kpOptions(q.knowledge_point)}</select>
        <div class="kp-desc" id="bat-kp-desc-${i}">${esc(kpDesc(q.knowledge_point))}</div>
      </td>
      <td><input type="number" step="0.5" min="0" value="${q.full_score}" oninput="updQ('bat',${i},'full_score',this.value)"></td>
      <td><button class="del-btn" onclick="delQ('bat',${i})">✕</button></td>
    </tr>`).join("");
}
$("#bat-add-q").addEventListener("click", () => {
  batQuestions.push({ qid: String(batQuestions.length + 1), qtype: "single", section_key: "lixue", full_score: 4, knowledge_point: "" });
  renderBatQuestions();
});

$("#bat-run").addEventListener("click", async () => {
  if (!batFile) return toast("请先上传答题数据 xlsx", true);
  const teacher = $("#bat-teacher").value;
  if (!teacher) return toast("请选择授课老师", true);
  if (!batQuestions.length) return toast("请先配置试卷题目", true);
  const emptyKp = batQuestions.filter((q) => !q.knowledge_point);
  if (emptyKp.length) return toast(`还有 ${emptyKp.length} 道题未选择考察知识点（必填）`, true);
  const payload = {
    file: batFile.file,
    teacher,
    mode: $("#bat-mode").value,
    exam_name: $("#bat-exam").value.trim(),
    questions: batQuestions.map((q) => ({ ...q, full_score: parseFloat(q.full_score) || 0 })),
  };
  try {
    const r = await api("/api/batch/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    lastJobId = r.job_id;
    $("#bat-result").classList.add("hidden");
    $("#bat-progress").classList.remove("hidden");
    $("#bat-progress-bar").style.width = "0%";
    $("#bat-progress-text").textContent = "任务已启动…";
    pollJob();
  } catch (err) { toast(err.message, true); }
});

function pollJob() {
  const timer = setInterval(async () => {
    try {
      const p = await api("/api/batch/progress/" + lastJobId);
      // 每个学生经历 计算/写HTML/导出 3 个阶段，done 会超过 total，用 min 归一化
      const pct = p.total ? Math.min(100, Math.round((p.done / p.total / 3) * 100)) : 0;
      const label = p.total ? `${Math.min(p.done, p.total)}/${p.total} 名学生（${pct}%）` : "";
      $("#bat-progress-bar").style.width = pct + "%";
      $("#bat-progress-text").textContent = `${label}${p.current ? " · " + esc(p.current) : ""}`;
      if (p.status === "done") {
        clearInterval(timer);
        showBatchResult(p.result);
      } else if (p.status === "error") {
        clearInterval(timer);
        $("#bat-progress").classList.add("hidden");
        toast("批量生成失败: " + (p.error || "未知错误"), true);
      }
    } catch (e) { /* 服务暂不可达，继续轮询 */ }
  }, 1500);
}

function showBatchResult(result) {
  $("#bat-progress").classList.add("hidden");
  lastResult = { rid: lastJobId, results: result.results };
  $("#bat-list tbody").innerHTML = result.results.map((s) => `
    <tr>
      <td>${s.rank || "-"}</td>
      <td>${esc(s.name)}</td>
      <td>${esc(s.class_type || "-")}</td>
      <td>${s.score} / ${s.full}</td>
      <td>${(s.rate * 100).toFixed(0)}%</td>
      <td>${s.pdf ? "✅" : "—"}</td>
      <td>${s.image ? "✅" : "—"}</td>
    </tr>`).join("");
  $("#bat-result").classList.remove("hidden");
  toast(`已为 ${result.count} 名学生生成报告（PDF + 图片）`);
}

/* ---- 导出对话框 ---- */
$("#bat-zip").addEventListener("click", () => {
  if (!lastResult.results || !lastResult.results.length) return toast("请先运行批量分析", true);
  $("#exp-names").innerHTML = lastResult.results.map((s) => `
    <label class="exp-item"><input type="checkbox" class="exp-chk" value="${esc(s.name)}" checked> ${esc(s.name)}（${s.score}/${s.full} 分）</label>`).join("");
  $("#export-modal").classList.remove("hidden");
});
$("#exp-all").addEventListener("change", (e) => {
  document.querySelectorAll(".exp-chk").forEach((c) => (c.checked = e.target.checked));
});
$("#exp-do").addEventListener("click", async () => {
  const names = [...document.querySelectorAll(".exp-chk:checked")].map((c) => c.value);
  if (!names.length) return toast("请至少选择一名学生", true);
  try {
    const r = await api("/api/batch/export", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rid: lastResult.rid, names, format: $("#exp-format").value }) });
    window.open(r.zip_url);
    $("#export-modal").classList.add("hidden");
    toast(`已导出 ${r.count} 份报告`);
  } catch (err) { toast(err.message, true); }
});
$("#exp-cancel").addEventListener("click", () => $("#export-modal").classList.add("hidden"));
$("#exp-cleanup").addEventListener("click", doCleanup);
$("#bat-cleanup").addEventListener("click", doCleanup);

async function doCleanup() {
  if (!confirm("确定清除所有已生成的报告与上传文件缓存？历史记录将一并清空，此操作不可恢复。")) return;
  try {
    await api("/api/cleanup", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reports: true, tmp: true, uploads: true }) });
    // 重置界面状态
    $("#bat-result").classList.add("hidden");
    $("#bat-progress").classList.add("hidden");
    $("#export-modal").classList.add("hidden");
    $("#bat-list tbody").innerHTML = "";
    lastResult = {};
    lastJobId = null;
    toast("缓存已清除");
  } catch (err) { toast(err.message, true); }
}

/* ================= 视频目录 ================= */
async function loadCatalog() {
  const ct = $("#cat-class").value;
  try {
    const r = await api("/api/catalog?class_type=" + encodeURIComponent(ct));
    catVideos = r.videos;
    renderCatalog();
  } catch (err) { toast(err.message, true); }
}
$("#cat-class").addEventListener("change", loadCatalog);

function kpOptionsAll(selected) {
  const sel = selected || [];
  return OUTLINE.map((sec) => sec.knowledge_points.map((kp) =>
    `<option value="${esc(kp.name)}" ${sel.includes(kp.name) ? "selected" : ""}>${esc(kp.name)}</option>`
  ).join("")).join("");
}
window.updCatKp = (i, el) => {
  catVideos[i].kp = [...el.selectedOptions].map((o) => o.value);
};

function renderCatalog() {
  const tb = $("#cat-tbl tbody");
  tb.innerHTML = catVideos.map((v, i) => `
    <tr>
      <td><input value="${esc(v.title)}" oninput="catVideos[${i}].title=this.value"></td>
      <td><select multiple size="3" class="kp-multi" onchange="updCatKp(${i},this)">${kpOptionsAll(v.kp)}</select></td>
      <td><input value="${esc(v.url)}" placeholder="选填" oninput="catVideos[${i}].url=this.value"></td>
      <td><button class="del-btn" onclick="catVideos.splice(${i},1);renderCatalog()">×</button></td>
    </tr>`).join("") || `<tr><td colspan="4" style="color:#99a">暂无视频，请上传目录截图 OCR 或手动添加</td></tr>`;
}
$("#cat-add").addEventListener("click", () => {
  catVideos.push({ title: "", url: "", kp: [] });
  renderCatalog();
});
$("#cat-auto").addEventListener("click", async () => {
  try {
    const r = await api("/api/catalog/auto-match", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ class_type: $("#cat-class").value }) });
    catVideos = r.videos;
    renderCatalog();
    toast(`自动匹配完成：${r.matched}/${r.total} 个视频已绑定知识点（请核对后保存）`);
  } catch (err) { toast(err.message, true); }
});
$("#cat-save").addEventListener("click", async () => {
  try {
    await api("/api/catalog/save", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ class_type: $("#cat-class").value, videos: catVideos.filter((v) => v.title.trim()) }) });
    toast("目录已保存");
  } catch (err) { toast(err.message, true); }
});
$("#cat-clear").addEventListener("click", async () => {
  if (!confirm("确定清空当前班型目录？")) return;
  await api("/api/catalog/clear", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ class_type: $("#cat-class").value }) });
  catVideos = [];
  renderCatalog();
});
$("#cat-img").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  e.target.value = "";
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  fd.append("class_type", $("#cat-class").value);
  try {
    const r = await api("/api/catalog/ocr", { method: "POST", body: fd });
    catVideos = r.videos;
    renderCatalog();
    toast(`OCR 识别完成，新增 ${r.new_count} 条，共 ${r.total} 条。请核对并保存`);
  } catch (err) { toast(err.message, true); }
});

/* ================= 设置 ================= */
$("#set-save").addEventListener("click", async () => {
  try {
    await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      engine_mode: $("#set-mode").value,
      school_name: $("#set-school").value.trim(),
      multi_choice_partial: $("#set-partial").value === "true",
      llm_api_key: $("#set-key").value.trim(),
      llm_base_url: $("#set-url").value.trim(),
      llm_model: $("#set-model").value.trim(),
    }) });
    $("#set-status").textContent = "✅ 已保存（注意：留空的 Key 不会被覆盖）";
    setTimeout(() => ($("#set-status").textContent = ""), 3200);
  } catch (err) { toast(err.message, true); }
});
$("#set-clear-key").addEventListener("click", async () => {
  if (!confirm("确定清除已保存的 API Key？清除后大模型模式将不可用。")) return;
  try {
    await api("/api/settings/clear-key", { method: "POST" });
    $("#set-key").value = "";
    $("#set-status").textContent = "✅ API Key 已清除";
    setTimeout(() => ($("#set-status").textContent = ""), 3200);
  } catch (err) { toast(err.message, true); }
});

/* 大纲导入 / 恢复（学科配置页） */
$("#cat-outline").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  e.target.value = "";
  if (!f) return;
  let data;
  try { data = JSON.parse(await f.text()); }
  catch (err) { return toast("JSON 解析失败，请检查文件格式", true); }
  const sections = data.sections || data;
  if (!Array.isArray(sections) || !sections.length) return toast("大纲内容为空（需 sections 数组）", true);
  try {
    const r = await api("/api/outline/import", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version: data.version || "import", sections }) });
    await loadOutline();
    $("#cat-outline-status").textContent = `✅ 已导入 ${r.knowledge_points} 个知识点`;
    toast("大纲导入成功");
  } catch (err) { toast("导入失败: " + err.message, true); }
});
$("#cat-outline-reset").addEventListener("click", async () => {
  if (!confirm("恢复内置高考物理大纲？自定义内容将被清除。")) return;
  try {
    await api("/api/outline/reset", { method: "POST" });
    await loadOutline();
    $("#cat-outline-status").textContent = "✅ 已恢复内置大纲";
    toast("已恢复内置大纲");
  } catch (err) { toast(err.message, true); }
});

/* ================= 历史 ================= */
async function loadHistory() {
  try {
    const rows = await api("/api/history");
    $("#his-tbl tbody").innerHTML = rows.map((r) => `
      <tr>
        <td>${esc(r.created_at)}</td>
        <td>${r.kind === "batch" ? "批量" : "个人"}</td>
        <td>${esc(r.teacher || "-")}</td>
        <td>${esc(r.student || "-")}</td>
        <td>${esc(r.class_type || "-")}</td>
        <td>${r.full ? `${r.score} / ${r.full}` : r.score}</td>
        <td>
          <a href="/api/reports/${r.id}/html" target="_blank">预览</a>
          <a href="/api/reports/${r.id}/pdf">PDF</a>
          ${r.kind === "batch" ? `<a href="/api/reports/${r.id}/zip">zip</a>` : `<a href="/api/reports/${r.id}/image">长图</a>`}
        </td>
      </tr>`).join("") || `<tr><td colspan="7" style="color:#99a">暂无记录</td></tr>`;
  } catch (err) { toast(err.message, true); }
}
