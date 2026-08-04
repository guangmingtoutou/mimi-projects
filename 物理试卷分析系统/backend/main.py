# -*- coding: utf-8 -*-
"""试卷分析系统 - 后端主应用（FastAPI）"""
import json
import re
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import Question, analyze, build_study_plan, grade_question
from .batch import parse_xlsx, run_batch
from .config import CATALOG_DIR, REPORT_DIR, STATIC_DIR, UPLOAD_DIR, clear_api_key, load_settings, save_settings
from .db import add_report, get_report, list_reports
from .exporters import html_to_long_image, html_to_pdf
from .knowledge import SECTIONS, QUESTION_TYPES, load_catalog, save_catalog
from .llm import analyze_paper_llm, llm_available, template_advice
from .ocr import ocr_available, ocr_video_list
from .paper_parser import extract_text, save_upload, split_questions
from .report_builder import build_html

app = FastAPI(title="试卷分析系统", version="0.1.0")

ALLOWED_PAPER = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".txt"}
ALLOWED_XLSX = {".xlsx", ".xls"}
ALLOWED_IMG = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


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
    """根据题目文本关键词自动匹配板块与知识点（规则引擎）"""
    from .knowledge import SECTIONS
    questions = payload.get("questions") or []
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
    return {"suggestions": suggestions}


# ---------------- 个人试卷分析 ----------------
def _run_analysis(questions: list[Question], meta: dict, mode: str) -> dict:
    class_type = meta.get("class_type", "目标班")
    analysis = analyze(questions)
    if mode in ("llm", "hybrid") and llm_available():
        try:
            advice = analyze_paper_llm(analysis, questions, class_type, load_catalog(class_type))
        except Exception as e:
            print(f"[warn] LLM 调用失败，回退模板: {e}")
            advice = template_advice(analysis)
    else:
        advice = template_advice(analysis)
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
    """payload: {file, teacher, class_type, mode, questions:[{qid,section_key,qtype,full_score,knowledge_point}]}"""
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
    paper_config = payload.get("questions") or []
    if not paper_config:
        raise HTTPException(400, "请先配置试卷题目信息")
    rid = uuid.uuid4().hex[:12]
    meta = {"report_id": rid, "teacher": teacher, "class_type": class_type,
            "school": load_settings().get("school_name", ""),
            "multi_partial": bool(load_settings().get("multi_choice_partial", False))}
    try:
        result = run_batch(parsed, teacher, paper_config, meta, mode=mode)
    except Exception as e:
        raise HTTPException(400, f"批量分析失败: {e}")
    add_report(rid, "batch", teacher, f"{result['count']}名学生", class_type,
               sum(r["score"] for r in result["results"]), 0,
               {"zip": result["zip_path"], "mode": mode})
    return {
        "report_id": rid,
        "count": result["count"],
        "results": result["results"],
        "zip_url": f"/api/reports/{rid}/zip",
        "zip_name": f"批量试卷分析_{teacher}_{rid[:6]}.zip",
    }


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
