# -*- coding: utf-8 -*-
"""试卷分析系统 - 后端主应用（FastAPI）"""
import json
import re
import shutil
import threading
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import Question, analyze, build_study_plan, grade_question
from .batch import parse_xlsx, run_batch
from .config import CATALOG_DIR, REPORT_DIR, STATIC_DIR, TMP_DIR, UPLOAD_DIR, clear_api_key, load_settings, save_settings
from .db import add_report, get_report, list_reports
from .exporters import html_to_long_image, html_to_pdf
from .knowledge import SECTIONS, QUESTION_TYPES, load_catalog, load_outline, reset_outline, save_catalog, save_outline
from .llm import analyze_paper_llm, llm_available, template_advice
from .ocr import ocr_available, ocr_video_list
from .paper_parser import extract_text, save_upload, split_questions
from .report_builder import build_html

app = FastAPI(title="试卷分析系统", version="0.5.0")

# 批量分析任务进度存储（内存）
BATCH_JOBS: dict = {}

ALLOWED_PAPER = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".txt"}
ALLOWED_XLSX = {".xlsx", ".xls"}
ALLOWED_IMG = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _valid_rid(rid: str) -> bool:
    """报告/任务 ID 安全校验（12 位十六进制）"""
    return bool(rid) and bool(re.fullmatch(r"[a-f0-9]{12}", rid))


@app.on_event("startup")
def _auto_open_browser():
    """服务启动后延迟 3 秒自动打开浏览器（绿色版体验；设 PAS_NO_BROWSER=1 可关闭）"""
    import os
    import threading
    import webbrowser
    if os.environ.get("PAS_NO_BROWSER") == "1":
        return
    def _open():
        try:
            webbrowser.open("http://127.0.0.1:8787")
        except Exception:
            pass
    threading.Timer(3.0, _open).start()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/files", StaticFiles(directory=str(UPLOAD_DIR)), name="files")


# ---------------- 设置 ----------------
@app.get("/api/settings")
def get_settings():
    s = load_settings()
    s["llm_available"] = llm_available()
    s["ocr_available"] = ocr_available()
    return s


@app.post("/api/settings")
def post_settings(payload: dict):
    return save_settings(payload)


@app.post("/api/settings/clear-key")
def clear_key():
    """显式清除 DeepSeek API Key（前端确认后调用）"""
    return clear_api_key()


# ---------------- 上传 ----------------
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_PAPER | ALLOWED_XLSX | ALLOWED_IMG:
        raise HTTPException(400, f"不支持的文件类型: {ext}")
    data = await file.read()
    name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    dest = UPLOAD_DIR / name
    dest.write_bytes(data)
    return {"filename": name, "url": f"/files/{name}", "original": file.filename, "ext": ext}


# ---------------- 知识库 ----------------
@app.get("/api/sections")
def get_sections():
    return {"sections": SECTIONS, "question_types": QUESTION_TYPES}


# ---------------- 知识大纲（高考物理） ----------------
@app.get("/api/outline")
def get_outline():
    """获取知识大纲（知识点 + 说明）"""
    return load_outline()


@app.post("/api/outline/import")
def import_outline(payload: dict):
    """导入/更新知识大纲。payload: {sections: [{key,name,knowledge_points:[{name,desc}]}]}"""
    sections = payload.get("sections") or []
    if not sections:
        raise HTTPException(400, "大纲内容为空")
    # 基本校验
    for sec in sections:
        if not sec.get("key") or not sec.get("name"):
            raise HTTPException(400, "板块缺少 key 或 name")
        for kp in sec.get("knowledge_points", []):
            if not kp.get("name"):
                raise HTTPException(400, "知识点缺少 name")
    outline = {"version": payload.get("version", "import"), "sections": sections}
    save_outline(outline)
    return {"ok": True, "sections": len(sections), "knowledge_points": sum(len(s.get("knowledge_points", [])) for s in sections)}


@app.post("/api/outline/reset")
def outline_reset():
    """恢复内置高考物理知识大纲"""
    outline = reset_outline()
    return {"ok": True, "sections": len(outline.get("sections", []))}


# ---------------- 缓存清理 ----------------
@app.post("/api/cleanup")
def cleanup(payload: dict = None):
    """清除生成的报告/临时文件/上传文件缓存（历史记录一并清空）"""
    payload = payload or {}
    targets = []
    if payload.get("reports", True):
        targets.append(REPORT_DIR)
    if payload.get("tmp", True):
        targets.append(TMP_DIR)
    if payload.get("uploads", False):
        targets.append(UPLOAD_DIR)
    cleared = 0
    for d in targets:
        if d.exists():
            for f in d.iterdir():
                if f.is_dir():
                    shutil.rmtree(f, ignore_errors=True)
                else:
                    f.unlink(missing_ok=True)
                cleared += 1
    from .db import _conn
    conn = _conn()
    conn.execute("DELETE FROM reports")
    conn.commit()
    conn.close()
    # 清空内存中的批量任务
    BATCH_JOBS.clear()
    return {"ok": True, "cleared": cleared}



@app.get("/api/catalog")
def get_catalog(class_type: str = "目标班"):
    return {"class_type": class_type, "videos": load_catalog(class_type), "ocr_available": ocr_available()}


@app.post("/api/catalog/ocr")
async def catalog_ocr(file: UploadFile = File(...), class_type: str = Form("目标班")):
    if not ocr_available():
        raise HTTPException(400, "未安装 OCR 组件（rapidocr-onnxruntime），请安装后重试")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMG:
        raise HTTPException(400, "目录图片仅支持图片格式")
    data = await file.read()
    name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    dest = CATALOG_DIR / name
    dest.write_bytes(data)
    try:
        videos = ocr_video_list(dest)
    except Exception as e:
        raise HTTPException(500, f"OCR 识别失败: {e}")
    # 与已有目录合并（按标题去重）
    existing = load_catalog(class_type)
    seen = {v["title"] for v in existing}
    for v in videos:
        if v["title"] not in seen:
            existing.append(v)
    save_catalog(class_type, existing)
    return {"videos": existing, "new_count": len(videos), "total": len(existing), "image": f"/files/{name}"}


@app.post("/api/catalog/save")
def catalog_save(payload: dict):
    class_type = payload.get("class_type", "目标班")
    videos = payload.get("videos", [])
    save_catalog(class_type, videos)
    return {"ok": True, "total": len(videos)}


@app.post("/api/catalog/clear")
def catalog_clear(payload: dict):
    class_type = payload.get("class_type", "目标班")
    save_catalog(class_type, [])
    return {"ok": True}


# ---------------- 试卷文本提取（供前端辅助配置） ----------------
@app.post("/api/paper/text")
async def paper_text(file: UploadFile = File(...)):
    data = await file.read()
    name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    dest = UPLOAD_DIR / name
    dest.write_bytes(data)
    text = extract_text(dest)
    questions = split_questions(text)
    return {"filename": name, "text": text[:8000], "questions": questions}


@app.post("/api/suggest/knowledge")
def suggest_knowledge(payload: dict):
    """根据题目文本匹配板块与知识点。优先使用大模型 API（配置了 Key 时），否则本地规则。"""
    from .knowledge import SECTIONS
    from .llm import suggest_knowledge_llm
    questions = payload.get("questions") or []
    # 1) 大模型优先
    if llm_available():
        try:
            sugg = suggest_knowledge_llm(questions)
            if sugg:
                return {"suggestions": sugg, "engine": "llm"}
        except Exception as e:
            print(f"[warn] LLM 标注失败，回退本地规则: {e}")
    # 2) 本地规则
    suggestions = []
    for item in questions:
        text = (item.get("text") or "") + (item.get("knowledge_point") or "")
        if not text.strip():
            continue
        best_sec, best_kp, best_score = None, None, 0
        for sec in SECTIONS:
            for kp in sec["knowledge_points"]:
                score = 0
                if kp["name"] in text:
                    score += 3
                for kw in kp["keywords"]:
                    if kw and kw in text:
                        score += 1
                if score > best_score:
                    best_sec, best_kp, best_score = sec["key"], kp["name"], score
        if best_sec and best_score > 0:
            suggestions.append({"qid": item.get("qid"), "section_key": best_sec, "knowledge_point": best_kp})
    return {"suggestions": suggestions, "engine": "rule"}


# ---------------- 个人试卷分析 ----------------
def _run_analysis(questions: list[Question], meta: dict, mode: str) -> dict:
    class_type = meta.get("class_type", "目标班")
    analysis = analyze(questions)
    if mode in ("llm", "hybrid") and llm_available():
        try:
            advice = analyze_paper_llm(analysis, questions, class_type, load_catalog(class_type),
                                       student=meta.get("student", ""))
        except Exception as e:
            print(f"[warn] LLM 调用失败，回退模板: {e}")
            advice = template_advice(analysis, student=meta.get("student", ""))
    else:
        advice = template_advice(analysis, student=meta.get("student", ""))
    plan = build_study_plan(analysis, class_type)
    return {"analysis": analysis, "advice": advice, "plan": plan}


@app.post("/api/analyze/individual")
def analyze_individual(payload: dict):
    """payload: {teacher, student, class_type, mode, questions:[{qid,section_key,qtype,full_score,got_score,knowledge_point}]}"""
    teacher = (payload.get("teacher") or "").strip()
    student = (payload.get("student") or "").strip()
    class_type = (payload.get("class_type") or "目标班").strip()
    mode = payload.get("mode") or load_settings().get("engine_mode", "rule")
    if mode not in ("rule", "llm", "hybrid"):
        mode = "rule"
    if not student:
        raise HTTPException(400, "请填写学生姓名")
    qs = payload.get("questions") or []
    if not qs:
        raise HTTPException(400, "请至少配置一道题")
    empty_kp = [str(q.get("qid", "?")) for q in qs if not (q.get("knowledge_point") or "").strip()]
    if empty_kp:
        raise HTTPException(400, f"以下题目未选择考察知识点（必填）：{'、'.join(empty_kp)}")
    questions = []
    for item in qs:
        q = Question(
            qid=str(item.get("qid", "")),
            section_key=item.get("section_key", "lixue"),
            qtype=item.get("qtype", "single"),
            full_score=float(item.get("full_score", 0) or 0),
            got_score=float(item.get("got_score", 0) or 0),
            knowledge_point=(item.get("knowledge_point") or "").strip(),
            student_answer=(item.get("student_answer") or "").strip(),
            correct_answer=(item.get("correct_answer") or "").strip(),
        )
        questions.append(q)

    rid = uuid.uuid4().hex[:12]
    meta = {"report_id": rid, "teacher": teacher, "student": student,
            "class_type": class_type, "school": load_settings().get("school_name", ""),
            "multi_partial": bool(load_settings().get("multi_choice_partial", False))}
    result = _run_analysis(questions, meta, mode)
    analysis = result["analysis"]
    html = build_html(analysis, meta, result["advice"], result["plan"], mode="individual")
    out_dir = REPORT_DIR / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    add_report(rid, "individual", teacher, student, class_type,
               analysis["total_got"], analysis["total_full"],
               {"mode": mode, "question_count": len(questions)})
    return {
        "report_id": rid,
        "score": analysis["total_got"],
        "full": analysis["total_full"],
        "rate": analysis["overall_rate"],
        "difficulty": analysis["overall_difficulty"],
        "html_url": f"/api/reports/{rid}/html",
        "pdf_url": f"/api/reports/{rid}/pdf",
        "image_url": f"/api/reports/{rid}/image",
    }


# ---------------- 批量试卷分析 ----------------
def _check_batch_prereqs(parsed: dict, teacher: str, class_type: str, mode: str, paper_config: list) -> list:
    """批量生成前检查：返回错误信息列表（空列表 = 全部通过）。
    1) 非纯规则模板必须已配置可用 API；2) 各题满分合计必须等于 100；3) 学生涉及的班型知识视频目录不能为空。
    """
    errors = []
    students = [s for s in parsed["students"] if s["teacher"] == teacher] if teacher else parsed["students"]
    if not students:
        return [f"老师「{teacher}」名下没有学生，请检查答题数据"]
    if mode in ("llm", "hybrid") and not llm_available():
        mode_name = "大模型 API" if mode == "llm" else "混合模式"
        errors.append(f"分析模式为「{mode_name}」，但未配置可用的 API Key。"
                      f"请到「设置」页配置 API Key，或将分析模式改为「纯规则模板」。")
    total_full = sum(float(q.get("full_score") or 0) for q in paper_config)
    if abs(total_full - 100) > 0.01:
        errors.append(f"试卷各题满分合计为 {total_full:g} 分，不是 100 分，请检查题目配置中的「满分」。")
    empty_types = sorted({(s.get("class_type") or "").strip() or class_type for s in students
                          if not load_catalog((s.get("class_type") or "").strip() or class_type)})
    if empty_types:
        errors.append(f"班型「{'、'.join(empty_types)}」的知识视频目录为空，报告将无法匹配强化学习视频。"
                      f"请先到「学科配置」页导入知识视频目录。")
    return errors


@app.post("/api/batch/preview")
async def batch_preview(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_XLSX:
        raise HTTPException(400, "答题数据仅支持 xlsx/xls")
    data = await file.read()
    name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    dest = UPLOAD_DIR / name
    dest.write_bytes(data)
    try:
        parsed = parse_xlsx(dest)
    except Exception as e:
        raise HTTPException(400, f"解析失败: {e}")
    return {
        "file": name,
        "teachers": parsed["teachers"],
        "student_count": len(parsed["students"]),
        "question_ids": parsed["question_ids"],
        "question_meta": parsed["question_meta"],
        "has_teacher_col": parsed["teacher_col"] is not None,
    }


@app.post("/api/batch/run")
def batch_run(payload: dict):
    """启动批量分析任务（异步）。payload: {file, teacher, class_type, mode, exam_name, questions:[...]}
    返回 job_id，进度通过 /api/batch/progress/{job_id} 轮询。"""
    fname = payload.get("file", "")
    dest = UPLOAD_DIR / Path(fname).name
    if not dest.exists():
        raise HTTPException(400, "答题数据文件不存在，请重新上传")
    try:
        parsed = parse_xlsx(dest)
    except Exception as e:
        raise HTTPException(400, f"解析失败: {e}")
    teacher = (payload.get("teacher") or "").strip()
    class_type = (payload.get("class_type") or "目标班").strip()
    mode = payload.get("mode") or load_settings().get("engine_mode", "rule")
    if mode not in ("rule", "llm", "hybrid"):
        mode = "rule"
    exam_name = (payload.get("exam_name") or "").strip()
    paper_config = payload.get("questions") or []
    if not paper_config:
        raise HTTPException(400, "请先配置试卷题目信息")
    empty_kp = [str(q.get("qid", "?")) for q in paper_config if not (q.get("knowledge_point") or "").strip()]
    if empty_kp:
        raise HTTPException(400, f"以下题目未选择考察知识点（必填）：{'、'.join(empty_kp)}")
    # —— 批量生成前检查（发现任何问题直接阻止生成）——
    prereq_errors = _check_batch_prereqs(parsed, teacher, class_type, mode, paper_config)
    if prereq_errors:
        raise HTTPException(400, "；".join(prereq_errors))
    rid = uuid.uuid4().hex[:12]
    meta = {"report_id": rid, "teacher": teacher, "class_type": class_type,
            "exam_name": exam_name,
            "school": load_settings().get("school_name", ""),
            "multi_partial": bool(load_settings().get("multi_choice_partial", False))}
    job = {"job_id": rid, "status": "running", "total": len(students := [s for s in parsed["students"] if s["teacher"] == teacher]) if teacher else len(parsed["students"]),
           "done": 0, "current": "", "error": None, "result": None}
    BATCH_JOBS[rid] = job

    def _progress_cb(done: int, total: int, current: str = ""):
        job["done"] = done
        job["total"] = total
        job["current"] = current

    def _worker():
        try:
            result = run_batch(parsed, teacher, paper_config, meta, mode=mode, progress_cb=_progress_cb)
            job["status"] = "done"
            job["result"] = result
            add_report(rid, "batch", teacher, f"{result['count']}名学生", class_type,
                       sum(r["score"] for r in result["results"]), 0,
                       {"zip": result["zip_path"], "mode": mode, "exam_name": exam_name})
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    threading.Thread(target=_worker, daemon=True).start()
    return {"job_id": rid, "status": "running", "total": job["total"]}


@app.get("/api/batch/progress/{job_id}")
def batch_progress(job_id: str):
    """查询批量任务进度"""
    if not _valid_rid(job_id):
        raise HTTPException(400, "无效的任务 ID")
    job = BATCH_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在或已过期（服务重启后需重新生成）")
    return {"job_id": job_id, "status": job["status"], "total": job["total"],
            "done": job["done"], "current": job["current"], "error": job["error"],
            "result": job["result"]}


@app.post("/api/batch/export")
def batch_export(payload: dict):
    """按需导出：选择学生 + 格式（pdf/图片/两者）。payload: {rid, names:[...], format:"pdf"|"image"|"both"}"""
    rid = str(payload.get("rid", ""))
    if not _valid_rid(rid):
        raise HTTPException(400, "无效的报告 ID")
    names = payload.get("names")  # None/空 = 全部学生
    fmt = payload.get("format", "pdf")
    if fmt not in ("pdf", "image", "both"):
        raise HTTPException(400, "格式仅支持 pdf / image / both")
    src_dir = REPORT_DIR / f"batch_{rid}"
    if not src_dir.exists():
        raise HTTPException(404, "批量结果不存在，请先运行批量分析")
    # 收集文件：name_safe + 格式
    files = {}
    for f in src_dir.iterdir():
        if f.suffix.lower() == ".pdf" and fmt in ("pdf", "both"):
            files.setdefault(f.stem, {})["pdf"] = f
        elif f.suffix.lower() in (".png", ".jpg") and fmt in ("image", "both"):
            if not f.name.endswith(".tall.png"):  # 过滤长图中间文件
                files.setdefault(f.stem, {})["image"] = f
    if names:
        name_set = {str(n).strip() for n in names if str(n).strip()}
        files = {k: v for k, v in files.items() if k in name_set or any(k.startswith(str(n)) for n in name_set)}
    if not files:
        raise HTTPException(400, "所选学生没有可导出的文件")
    out_zip = REPORT_DIR / f"export_{rid}_{uuid.uuid4().hex[:6]}.zip"
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for stem, m in sorted(files.items()):
            for kind, f in m.items():
                suffix = ".pdf" if kind == "pdf" else ".png"
                zf.write(f, f"{stem}{suffix}")
    return {"zip_url": f"/api/export/{out_zip.name}", "count": len(files)}


@app.get("/api/export/{zname}")
def export_file(zname: str):
    """下载按需导出的 zip"""
    if not re.fullmatch(r"export_[a-f0-9]{12}_[a-f0-9]{6}\.zip", zname):
        raise HTTPException(400, "无效的文件名")
    p = REPORT_DIR / zname
    if not p.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(p, media_type="application/zip", filename=zname)


# ---------------- 报告导出 ----------------
@app.get("/api/reports/{rid}/html")
def report_html(rid: str):
    p = REPORT_DIR / rid / "report.html"
    if not p.exists():
        raise HTTPException(404, "报告不存在")
    return FileResponse(p, media_type="text/html")


@app.get("/api/reports/{rid}/pdf")
def report_pdf(rid: str):
    out_dir = REPORT_DIR / rid
    pdf = out_dir / "report.pdf"
    html = out_dir / "report.html"
    if not html.exists():
        raise HTTPException(404, "报告不存在")
    if not pdf.exists():
        try:
            html_to_pdf(html, pdf)
        except Exception as e:
            raise HTTPException(500, f"PDF 导出失败: {e}")
    return FileResponse(pdf, media_type="application/pdf", filename=f"{rid}_试卷分析报告.pdf")


@app.get("/api/reports/{rid}/image")
def report_image(rid: str):
    out_dir = REPORT_DIR / rid
    img = out_dir / "report.png"
    html = out_dir / "report.html"
    if not html.exists():
        raise HTTPException(404, "报告不存在")
    if not img.exists():
        try:
            html_to_long_image(html, img)
        except Exception as e:
            raise HTTPException(500, f"长图导出失败: {e}")
    return FileResponse(img, media_type="image/png", filename=f"{rid}_试卷分析报告.png")


@app.get("/api/reports/{rid}/zip")
def report_zip(rid: str):
    rec = get_report(rid)
    if not rec or rec["kind"] != "batch":
        raise HTTPException(404, "批量报告不存在")
    meta = json.loads(rec["meta"])
    zpath = Path(meta.get("zip", ""))
    if not zpath.exists():
        raise HTTPException(404, "压缩包不存在")
    return FileResponse(zpath, media_type="application/zip",
                        filename=f"批量试卷分析_{rec['teacher']}_{rid[:6]}.zip")


@app.get("/api/history")
def history(kind: str | None = None):
    return list_reports(kind, limit=50)


@app.delete("/api/reports/{rid}")
def delete_report(rid: str):
    # 安全校验：rid 只允许 12 位十六进制，防止路径穿越删除任意目录
    if not re.fullmatch(r"[a-f0-9]{12}", rid):
        raise HTTPException(400, "无效的报告 ID")
    from .db import _conn
    out_dir = REPORT_DIR / rid
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    conn = _conn()
    conn.execute("DELETE FROM reports WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return {"ok": True}
