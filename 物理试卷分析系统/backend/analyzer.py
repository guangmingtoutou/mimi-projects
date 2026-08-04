# -*- coding: utf-8 -*-
"""规则分析引擎：得分统计、板块/题型汇总、难度评估、知识点丢分聚合"""
import re
from dataclasses import dataclass, field
from typing import Optional

from .knowledge import SECTIONS, SECTION_INDEX, TYPE_INDEX, match_videos


@dataclass
class Question:
    """一道题的作答信息"""
    qid: str                    # 题号，如 "1"、"13(1)"
    section_key: str            # 板块 key
    qtype: str                  # 题型 key
    full_score: float           # 满分
    knowledge_point: str = ""   # 考察知识点（可空，由规则/大模型补充）
    student_answer: str = ""    # 学生答案
    correct_answer: str = ""    # 正确答案
    got_score: float = 0.0      # 得分
    partial_score: Optional[float] = None  # 多选题“选对但不全”的固定得分


_CHOICE_RE = re.compile(r"[A-Da-d]")
_OPT_RE = re.compile(r"^\s*([A-Da-d])\s*[：:]")


def _norm_choices(s: str) -> str:
    """'A,C'、'C,A'、'A、C' → 'AC'（去重排序）"""
    letters = _CHOICE_RE.findall(s or "")
    return "".join(sorted(set(c.upper() for c in letters)))


def _opt_letter(s: str) -> str | None:
    """主观题答案 'C：f=4N a=1m/s²' → 选项字母 'C'；纯单字母 'C' → 'C'"""
    m = _OPT_RE.match(s or "")
    if m:
        return m.group(1).upper()
    t = (s or "").strip()
    if re.fullmatch(r"[A-Da-d]", t):
        return t.upper()
    return None


def _norm_str(s: str) -> str:
    """宽松字符串规范化（去空白、统一标点/上下标）"""
    t = (s or "").strip().lower()
    t = re.sub(r"[\s　]+", "", t)
    t = t.replace("，", ",").replace("；", ";").replace("：", ":")
    t = t.replace("²", "^2").replace("√", "sqrt")
    return t


def grade_question(q: Question, multi_partial: bool = False) -> float:
    """判定得分。
    - 单选：字母一致即满分
    - 多选：全部选对=满分；选对但不全=partial_score（若启用）；有选错=0
    - 主观题：优先比较选项字母；无选项字母时做规范化字符串比较
    """
    if q.full_score <= 0:
        return 0.0
    sa = (q.student_answer or "").strip()
    ca = (q.correct_answer or "").strip()
    if not sa:
        return 0.0
    if q.qtype == "multi":
        s_set, c_set = _norm_choices(sa), _norm_choices(ca)
        if not s_set or not c_set:
            return 0.0
        if s_set == c_set:
            return q.full_score
        if multi_partial and q.partial_score is not None and set(s_set) <= set(c_set):
            return min(q.partial_score, q.full_score)
        return 0.0
    if q.qtype == "calculation":
        s_opt, c_opt = _opt_letter(sa), _opt_letter(ca)
        if s_opt and c_opt:
            return q.full_score if s_opt == c_opt else 0.0
        if not c_opt:
            return q.full_score if _norm_str(sa) == _norm_str(ca) else 0.0
        return 0.0
    # 单选/其他：字母或规范化字符串比较
    s_letters, c_letters = _norm_choices(sa), _norm_choices(ca)
    if s_letters and c_letters:
        return q.full_score if s_letters == c_letters else 0.0
    return q.full_score if _norm_str(sa) == _norm_str(ca) else 0.0


def difficulty_label(rate: float) -> str:
    if rate >= 0.85:
        return "容易"
    if rate >= 0.6:
        return "中等"
    if rate >= 0.4:
        return "较难"
    return "困难"


def analyze(questions: list[Question]) -> dict:
    """对一组成绩数据做规则统计，返回结构化分析结果"""
    total_full = sum(q.full_score for q in questions) or 1
    total_got = sum(q.got_score for q in questions)
    overall_rate = total_got / total_full
    overall_difficulty = difficulty_label(overall_rate)

    # 每道题得分率
    per_question = []
    for q in questions:
        rate = q.got_score / q.full_score if q.full_score else 0
        per_question.append({
            "qid": q.qid,
            "section": SECTION_INDEX.get(q.section_key, {}).get("name", q.section_key),
            "section_key": q.section_key,
            "qtype": TYPE_INDEX.get(q.qtype, {}).get("name", q.qtype),
            "qtype_key": q.qtype,
            "full_score": q.full_score,
            "got_score": q.got_score,
            "lost_score": round(q.full_score - q.got_score, 1),
            "rate": round(rate, 3),
            "difficulty": difficulty_label(rate),
            "knowledge_point": q.knowledge_point,
            "student_answer": q.student_answer,
            "correct_answer": q.correct_answer,
            "correct": q.got_score >= q.full_score,
        })

    # 板块汇总
    sections = []
    for sec in SECTIONS:
        qs = [q for q in questions if q.section_key == sec["key"]]
        if not qs:
            continue
        full = sum(q.full_score for q in qs)
        got = sum(q.got_score for q in qs)
        lost = full - got
        rate = got / full if full else 0
        sections.append({
            "key": sec["key"],
            "name": sec["name"],
            "gaokao_weight": sec["gaokao_weight"],
            "importance": sec["importance"],
            "full_score": round(full, 1),
            "got_score": round(got, 1),
            "lost_score": round(lost, 1),
            "rate": round(rate, 3),
            "difficulty": difficulty_label(rate),
            "questions": [q for q in per_question if q["section_key"] == sec["key"]],
            "loss_questions": [q for q in per_question if q["section_key"] == sec["key"] and q["lost_score"] > 0],
        })
    sections.sort(key=lambda s: -s["lost_score"])

    # 题型汇总
    qtypes = []
    for t in TYPE_INDEX.values():
        qs = [q for q in questions if q.qtype == t["key"]]
        if not qs:
            continue
        full = sum(q.full_score for q in qs)
        got = sum(q.got_score for q in qs)
        qtypes.append({
            "key": t["key"],
            "name": t["name"],
            "full_score": round(full, 1),
            "got_score": round(got, 1),
            "lost_score": round(full - got, 1),
            "rate": round(got / full, 3) if full else 0,
        })

    # 知识点丢分聚合
    kp_loss = {}
    for q in per_question:
        if q["lost_score"] <= 0 or not q["knowledge_point"]:
            continue
        item = kp_loss.setdefault(q["knowledge_point"], {
            "knowledge_point": q["knowledge_point"],
            "section": q["section"],
            "section_key": q["section_key"],
            "lost_score": 0.0,
            "full_score": 0.0,
            "questions": [],
        })
        item["lost_score"] = round(item["lost_score"] + q["lost_score"], 1)
        item["full_score"] = round(item["full_score"] + q["full_score"], 1)
        item["questions"].append({"qid": q["qid"], "lost": q["lost_score"], "got": q["got_score"], "full": q["full_score"]})
    kp_list = sorted(kp_loss.values(), key=lambda x: -x["lost_score"])

    # 强化学习计划：丢分知识点 → 知识视频（由上层传入 class_type 填充）
    return {
        "total_full": round(total_full, 1),
        "total_got": round(total_got, 1),
        "total_lost": round(total_full - total_got, 1),
        "overall_rate": round(overall_rate, 3),
        "overall_difficulty": overall_difficulty,
        "per_question": per_question,
        "sections": sections,
        "qtypes": qtypes,
        "knowledge_loss": kp_list,
    }


def build_study_plan(analysis: dict, class_type: str) -> list:
    """丢分知识点 → 对应知识视频，生成强化学习计划"""
    plan = []
    for kp in analysis.get("knowledge_loss", []):
        videos = match_videos(kp["knowledge_point"], class_type)
        plan.append({
            "knowledge_point": kp["knowledge_point"],
            "section": kp["section"],
            "lost_score": kp["lost_score"],
            "questions": kp["questions"],
            "videos": videos,
            "has_videos": bool(videos),
        })
    return plan
