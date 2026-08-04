# -*- coding: utf-8 -*-
"""大模型引擎：DeepSeek API（OpenAI 兼容协议），用于难度分析、知识点补充、建议文案"""
import json

import requests

from .config import load_settings

SYSTEM_PROMPT = """你是一名资深高考物理教师和学情分析师。请根据提供的试卷信息、学生作答与得分情况，输出专业、具体、有温度的学情分析。
要求：
1. 分析必须基于给出的数据，不得编造题目和分数。
2. 知识点名称使用规范的高考物理术语。
3. 建议要具体可执行，鼓励语气真诚自然，不空洞。
4. 所有输出使用简体中文。"""


def _client():
    s = load_settings()
    return s


def llm_available() -> bool:
    s = _client()
    return bool(s.get("llm_api_key"))


def chat_json(messages: list, temperature: float = 0.7, timeout: int = 120) -> dict:
    """调用大模型并解析 JSON 输出"""
    s = _client()
    base = s.get("llm_base_url", "https://api.deepseek.com").rstrip("/")
    url = base + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {s.get('llm_api_key', '')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": s.get("llm_model", "deepseek-chat"),
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def build_paper_context(analysis: dict, questions_meta: list, class_type: str, videos: list) -> str:
    """组装发给大模型的上下文文本"""
    lines = []
    lines.append(f"班型：{class_type}")
    lines.append(f"总分：{analysis['total_got']}/{analysis['total_full']}，得分率 {analysis['overall_rate']:.0%}")
    lines.append("各板块得分：")
    for sec in analysis["sections"]:
        lines.append(f"- {sec['name']}：{sec['got_score']}/{sec['full_score']}（得分率{sec['rate']:.0%}，丢分{sec['lost_score']}）")
    lines.append("各题型得分：")
    for t in analysis["qtypes"]:
        lines.append(f"- {t['name']}：{t['got_score']}/{t['full_score']}（得分率{t['rate']:.0%}）")
    lines.append("逐题情况（题号/板块/题型/满分/得分/知识点/学生答案/正确答案）：")
    for q in analysis["per_question"]:
        lines.append(
            f"- {q['qid']}（{q['section']}·{q['qtype']}）{q['got_score']}/{q['full_score']}分 "
            f"知识点:{q['knowledge_point'] or '未标注'} 学生答案:{q['student_answer'] or '空'} 正确答案:{q['correct_answer']}"
        )
    if videos:
        lines.append("该班型可用的知识视频目录：")
        for v in videos[:80]:
            lines.append(f"- {v.get('title', '')}")
    return "\n".join(lines)


def analyze_paper_llm(analysis: dict, questions_meta: list, class_type: str, videos: list, student: str = "") -> dict:
    """大模型生成：试卷难度评析、知识点补充、强化建议、鼓励语"""
    context = build_paper_context(analysis, questions_meta, class_type, videos)
    call = student_call(student)
    user_msg = f"""请基于以下学情数据输出 JSON（严格按此结构）：
{{
  "paper_comment": "试卷整体分析（约350字：整体难度与得分率，各板块强弱，选择题/非选择题表现，主要失分点，复习方向）",
  "section_importance": "各板块在高考中的占比与重要性说明（150字内）",
  "knowledge_supplement": [{{"qid": "题号", "knowledge_point": "规范知识点名称"}}],
  "study_advice": "后续学习建议（约150字，围绕完成直播课、观看知识视频展开）",
  "encouragement": "一段真诚的鼓励（约100字，以「{call}」开头，使用学生称呼）"
}}
学情数据：
{context}"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    return chat_json(messages)


def student_call(name: str) -> str:
    """学生称呼：两个字直接“XX同学”；超过两个字取后两个字加“同学”"""
    n = (name or "").strip()
    if not n:
        return "同学"
    if len(n) <= 2:
        return f"{n}同学"
    return f"{n[-2:]}同学"


def template_advice(analysis: dict, student: str = "") -> dict:
    """纯规则模式的模板化建议文案（不依赖网络）"""
    sec = analysis["sections"]
    total = analysis["total_got"]
    full = analysis["total_full"]
    rate = analysis["overall_rate"]
    choice_rate = analysis.get("choice_rate", 0)
    non_rate = analysis.get("nonchoice_rate", 0)

    # 试卷整体分析（~350字）
    pts = []
    pts.append(f"本次试卷满分{full:.0f}分，得分{total:.0f}分，整体得分率{rate:.0%}，难度评定为「{analysis['overall_difficulty']}”。")
    if sec:
        weak = [s for s in sec if s["rate"] < 0.6]
        strong = [s for s in sec if s["rate"] >= 0.7]
        if weak:
            pts.append(f"从板块分布看，{('、'.join(s['name'] for s in weak[:3]))}等板块失分较多，且这些板块在高考中占比可观，是当前复习必须优先补强的短板。")
        if strong:
            pts.append(f"{('、'.join(s['name'] for s in strong[:2]))}等板块掌握较好，说明基础概念与常规题型训练已有成效。")
    pts.append(f"从题型结构看，选择题得分率{choice_rate:.0%}，非选择题得分率{non_rate:.0%}，非选择题（实验题与计算题）失分相对集中，反映解题步骤规范性、过程书写与综合建模能力仍需加强。")
    if sec and weak:
        w = weak[0]
        kps = set(q["knowledge_point"] for q in w["loss_questions"] if q.get("knowledge_point"))
        if kps:
            pts.append(f"丢分最集中的板块是「{w['name']}」，涉及{('、'.join(list(kps)[:3]))}等知识点，建议结合错题逐一回看对应知识视频，再通过同类题巩固。")
    pts.append("总体来看，基础知识掌握较为扎实，后续复习应以错题为抓手、以视频课为工具，稳步提升综合题得分能力。")
    paper_comment = "".join(pts)

    # 鼓励语（~100字，带学生称呼）
    call = student_call(student)
    encouragement = (
        f"{call}，这次拿到了{total:.0f}分，你的努力正在被看见！分数只是阶段性的坐标，"
        "错题才是成长的阶梯。接下来的复习，建议优先完成直播课，把丢分板块对应的知识视频逐个看一遍，"
        "再配合同类题巩固。坚持下去，下一次一定会更稳。加油！"
    )

    # 后续建议（围绕直播课、知识视频）
    study_advice = (
        "后续建议：① 按本报告的强化学习计划，优先完成对应直播课的学习；"
        "② 每天安排固定时间观看丢分知识点匹配的知识视频，边看边做笔记；"
        "③ 每学完一个知识点，完成3~5道同类题检验掌握效果；"
        "④ 每周复盘一次错题，确保同类题型不再丢分。"
    )

    return {
        "paper_comment": paper_comment,
        "section_importance": "力学与电磁学在高考物理中合计约占70%的分值，是拉分关键；热学、光学、原子物理以基础概念为主，属于必须拿稳的送分板块；实验题渗透在各板块中，注重原理与数据处理能力。",
        "knowledge_supplement": [],
        "study_advice": study_advice,
        "encouragement": encouragement,
    }
