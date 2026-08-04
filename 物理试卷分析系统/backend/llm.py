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


def analyze_paper_llm(analysis: dict, questions_meta: list, class_type: str, videos: list) -> dict:
    """大模型生成：试卷难度评析、知识点补充、强化建议、鼓励语"""
    context = build_paper_context(analysis, questions_meta, class_type, videos)
    user_msg = f"""请基于以下学情数据输出 JSON（严格按此结构）：
{{
  "paper_comment": "试卷整体难度评析（结合得分率与板块结构，150字内）",
  "section_importance": "各板块在高考中的占比与重要性说明（150字内）",
  "knowledge_supplement": [{{"qid": "题号", "knowledge_point": "规范知识点名称"}}],
  "study_advice": "针对主要丢分板块的强化学习建议（200字内，可提及对应知识视频标题）",
  "encouragement": "一段真诚的鼓励和后续学习建议（120字内）"
}}
学情数据：
{context}"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    return chat_json(messages)


def template_advice(analysis: dict) -> dict:
    """纯规则模式的模板化建议文案（不依赖网络）"""
    sec = analysis["sections"]
    worst = sec[0] if sec else None
    best = sec[-1] if sec else None
    total = analysis["total_got"]
    full = analysis["total_full"]
    rate = analysis["overall_rate"]

    if rate >= 0.85:
        level = "非常出色"
    elif rate >= 0.7:
        level = "良好"
    elif rate >= 0.5:
        level = "中等"
    elif rate >= 0.3:
        level = "偏弱"
    else:
        level = "薄弱"

    lines = []
    lines.append(f"本次试卷总分 {total} 分（满分 {full} 分），得分率 {rate:.0%}，整体表现{level}。")
    if worst:
        lines.append(f"丢分最集中的板块是「{worst['name']}」，共丢 {worst['lost_score']:.0f} 分，是后续复习的重中之重。")
    if best and best["full_score"] > 0 and best["rate"] >= 0.7 and best["key"] != (worst or {}).get("key"):
        lines.append(f"「{best['name']}」板块掌握得不错，请继续保持。")

    paper_comment = lines[0] + (" " + lines[1] if len(lines) > 1 else "")
    study_advice = " ".join(lines[1:]) if len(lines) > 1 else "建议按板块逐一梳理错题，先看对应知识视频，再做同类题巩固。"
    encouragement = (
        f"这次拿到了 {total} 分，你的努力正在被看见。分数只是暂时的坐标，"
        "错题才是进步的阶梯——把每一道丢分题都变成会做的题，下一次一定更稳。继续加油！"
    )
    return {
        "paper_comment": paper_comment,
        "section_importance": "力学与电磁学在高考物理中合计约占70%的分值，是拉分关键；热学、光学、原子物理以基础概念为主，属于必须拿稳的送分板块；实验题渗透在各板块中，注重原理与数据处理能力。",
        "knowledge_supplement": [],
        "study_advice": study_advice,
        "encouragement": encouragement,
    }
