# -*- coding: utf-8 -*-
"""试卷解析：PDF / Word / 图片 导入，题目切分、分值提取（尽力而为）"""
import re
from pathlib import Path

from .config import UPLOAD_DIR


def save_upload(file_bytes: bytes, filename: str) -> Path:
    """保存上传文件到 uploads，返回路径"""
    safe = Path(filename).name
    dest = UPLOAD_DIR / safe
    dest.write_bytes(file_bytes)
    return dest


def extract_text(path: Path) -> str:
    """从 PDF / Word / txt 提取文本；图片返回空串"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix in (".docx", ".doc"):
        return _docx_text(path)
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return ""


def _docx_text(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


# 题号匹配：数字后跟点/顿号/右括号，如 "1." "13." "1、" "1）"
QID_RE = re.compile(r"^\s*(\d{1,3})\s*[.、)．]")
# 分值匹配：如 (10分) 10分 共10分
SCORE_RE = re.compile(r"[（(]\s*(\d{1,3}(?:\.\d)?)\s*分\s*[)）]|共\s*(\d{1,3}(?:\.\d)?)\s*分|(\d{1,3}(?:\.\d)?)\s*分$")


def split_questions(text: str) -> list[dict]:
    """把试卷文本按题号切分为题目列表，尝试提取分值"""
    if not text.strip():
        return []
    lines = text.splitlines()
    questions = []
    cur = None
    for line in lines:
        m = QID_RE.match(line)
        if m:
            if cur:
                questions.append(cur)
            cur = {"qid": m.group(1), "text": line.strip()}
        elif cur:
            cur["text"] += "\n" + line.strip()
    if cur:
        questions.append(cur)
    for q in questions:
        m = SCORE_RE.search(q["text"])
        if m:
            score = m.group(1) or m.group(2) or m.group(3)
            q["score"] = float(score)
        else:
            q["score"] = None
    return questions


def guess_type_from_qid(qid: str, multi_qids: set, experiment_qids: set, calc_qids: set) -> str:
    """根据题号范围推测题型（单选/多选/实验/计算），由调用方传入各区段题号集合"""
    if qid in multi_qids:
        return "multi"
    if qid in experiment_qids:
        return "experiment"
    if qid in calc_qids:
        return "calculation"
    return "single"


def parse_section_ranges(text: str) -> dict:
    """尝试从试卷文本识别板块/题型区段标题，返回 {'multi': {'start':..,'end':..}, ...}"""
    result = {}
    labels = {
        "multi": ["多项选择", "多选题", "不定项"],
        "experiment": ["实验题", "实验"],
        "calculation": ["计算题", "解答题", "论述计算"],
        "fill": ["填空题", "填空"],
    }
    for key, kws in labels.items():
        for m in re.finditer(r"(?m)^.*?(" + "|".join(kws) + r").*?$", text):
            result.setdefault(key, {"start": None, "end": None, "line": m.group(0)})
    return result
