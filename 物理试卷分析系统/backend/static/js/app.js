/* 试卷分析系统 - 前端逻辑 */
"use strict";

const $ = (sel) => document.querySelector(sel);

let SECTIONS = [];
let QTYPES = [];
let indFiles = [];          // 个人分析上传的试卷文件
let indQuestions = [];      // 个人分析题目配置
let batFile = null;         // 批量 xlsx 文件信息
let batPaper = null;        // 批量试卷文件信息
let batQuestions = [];      // 批量题目配置
let batPaperQuestions = []; // 批量试卷提取出的题目（含原文）
let indPaperQuestions = []; // 个人试卷提取出的题目（含原文）
let catVideos = [];         // 当前班型视频目录
let lastResult = {};        // 最近生成的报告

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
    renderIndQuestions();
    renderBatQuestions();
  } catch (e) { toast("初始化失败: " + e.message, true); }
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
      <td><select onchange="updQ('ind',${i},'qtype',this.value)">${typeOptions(q.qtype)}</select></td>
      <td><select onchange="updQ('ind',${i},'section_key',this.value)">${sectionOptions(q.section_key)}</select></td>
      <td><input type="number" step="0.5" min="0" value="${q.full_score}" oninput="updQ('ind',${i},'full_score',this.value)"></td>
      <td><input type="number" step="0.5" min="0" value="${q.got_score}" oninput="updQ('ind',${i},'got_score',this.value)"></td>
      <td><input type="text" readonly value="${+q.got_score >= +q.full_score ? "✓ 正确" : "✗ 错题"}" style="text-align:center"></td>
      <td><input value="${esc(q.knowledge_point)}" oninput="updQ('ind',${i},'knowledge_point',this.value)"></td>
      <td><button class="del-btn" onclick="delQ('ind',${i})">×</button></td>
    </tr>`).join("");
}
window.updQ = (mode, i, field, val) => {
  const arr = mode === "ind" ? indQuestions : batQuestions;
  arr[i][field] = val;
  if (mode === "ind" && (field === "got_score" || field === "full_score")) renderIndQuestions();
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
    toast(`已提取 ${indQuestions.length} 道题，请核对题型/板块/分值`);
    renderIndQuestions();
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

/* 智能标注知识点：根据试卷原文关键词匹配板块与知识点 */
async function suggestKnowledge(mode) {
  const arr = mode === "ind" ? indQuestions : batQuestions;
  const paperQs = mode === "ind" ? indPaperQuestions : batPaperQuestions;
  if (!paperQs.length) return toast("请先上传试卷并点击「从试卷提取题目」", true);
  const textByQid = {};
  for (const pq of paperQs) textByQid[String(pq.qid)] = pq.text || "";
  const payload = { questions: arr.map((q) => ({ qid: q.qid, text: textByQid[String(q.qid)] || "" })) };
  try {
    const r = await api("/api/suggest/knowledge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    let n = 0;
    for (const sug of r.suggestions) {
      const q = arr.find((x) => String(x.qid) === String(sug.qid));
      if (q) {
        q.section_key = sug.section_key;
        q.knowledge_point = sug.knowledge_point;
        n++;
      }
    }
    if (mode === "ind") renderIndQuestions(); else renderBatQuestions();
    toast(`已标注 ${n} 道题（关键词匹配），请核对`);
  } catch (err) { toast("标注失败: " + err.message, true); }
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
    // 用表头信息自动填充题目配置（题型/默认分值来自表格）
    batQuestions = (r.question_meta || []).map((m) => ({
      qid: m.qid,
      qtype: m.qtype || "single",
      section_key: "lixue",
      full_score: m.default_score || "",
      knowledge_point: "",
    }));
    toast(`已自动识别 ${batQuestions.length} 道题（题型/分值来自表格），请补充板块和知识点`);
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
    // 与已有配置（来自 xlsx 表头）按题号合并：有分值则填入，缺失则追加
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
      batQuestions = batQuestions.filter((q) => String(q.qid) !== pid); // 大题已拆分，不再单独计分
    }
    toast(`已合并试卷信息，共 ${batQuestions.length} 道题，请核对题型/板块/分值`);
    renderBatQuestions();
  } catch (err) { toast("提取失败: " + err.message, true); }
});

function renderBatQuestions() {
  const tb = $("#bat-qtbl tbody");
  tb.innerHTML = batQuestions.map((q, i) => `
    <tr data-i="${i}">
      <td><input value="${esc(q.qid)}" oninput="updQ('bat',${i},'qid',this.value)"></td>
      <td><select onchange="updQ('bat',${i},'qtype',this.value)">${typeOptions(q.qtype)}</select></td>
      <td><select onchange="updQ('bat',${i},'section_key',this.value)">${sectionOptions(q.section_key)}</select></td>
      <td><input type="number" step="0.5" min="0" value="${q.full_score}" oninput="updQ('bat',${i},'full_score',this.value)"></td>
      <td><input value="${esc(q.knowledge_point)}" oninput="updQ('bat',${i},'knowledge_point',this.value)"></td>
      <td><button class="del-btn" onclick="delQ('bat',${i})">×</button></td>
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
  const payload = {
    file: batFile.file,
    teacher,
    class_type: $("#bat-class").value,
    mode: $("#bat-mode").value,
    questions: batQuestions.map((q) => ({ ...q, full_score: parseFloat(q.full_score) || 0 })),
  };
  try {
    const r = await api("/api/batch/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    lastResult = r;
    $("#bat-list tbody").innerHTML = r.results.map((s) => `
      <tr><td>${s.rank || "-"}</td><td>${esc(s.name)}</td><td>${s.score} / ${s.full}</td><td>${(s.rate * 100).toFixed(0)}%</td>
      <td><a href="${r.zip_url}">查看（打包下载）</a></td></tr>`).join("");
    $("#bat-result").classList.remove("hidden");
    toast(`已为 ${r.count} 名学生生成报告`);
  } catch (err) { toast(err.message, true); }
});
$("#bat-zip").addEventListener("click", () => window.open(lastResult.zip_url));

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

function renderCatalog() {
  $("#cat-tbl tbody").innerHTML = catVideos.map((v, i) => `
    <tr>
      <td><input value="${esc(v.title)}" oninput="catVideos[${i}].title=this.value"></td>
      <td><input value="${esc(v.url)}" placeholder="选填" oninput="catVideos[${i}].url=this.value"></td>
      <td><button class="del-btn" onclick="catVideos.splice(${i},1);renderCatalog()">×</button></td>
    </tr>`).join("") || `<tr><td colspan="3" style="color:#99a">暂无视频，请上传目录截图 OCR 或手动添加</td></tr>`;
}
$("#cat-add").addEventListener("click", () => {
  catVideos.push({ title: "", url: "" });
  renderCatalog();
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
