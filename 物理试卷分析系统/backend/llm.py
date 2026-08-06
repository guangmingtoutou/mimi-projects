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


def build_paper_context(analysis: dict, questions_meta: list, class_type: str, videos: list,
                        personal: bool = False) -> str:
    """组装发给大模型的上下文文本。personal=True：无分数，按对/错题与正确率描述"""
    lines = []
    lines.append(f"班型：{class_type}")
    if personal:
        total, got, wrong_n = analysis["total_full"], analysis["total_got"], analysis["total_lost"]
        lines.append(f"试卷共 {total:g} 题，做对 {got:g} 题，做错 {wrong_n:g} 题，正确率 {analysis['overall_rate']:.0%}（无分数，错题由老师标记）")
        lines.append("各板块掌握情况（题数/做对/正确率/错题数）：")
        for sec in analysis["sections"]:
            lines.append(f"- {sec['name']}：共{sec['full_score']:g}题，做对{sec['got_score']:g}题（正确率{sec['rate']:.0%}，错{sec['lost_score']:g}题）")
        lines.append("逐题情况（题号/板块/题型/对错/知识点）：")
        for q in analysis["per_question"]:
            mark = "对" if q["correct"] else "错"
            lines.append(f"- {q['qid']}（{q['section']}·{q['qtype']}）{mark} 知识点:{q['knowledge_point'] or '未标注'}")
    else:
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


def analyze_paper_llm(analysis: dict, questions_meta: list, class_type: str, videos: list,
                      student: str = "", personal: bool = False) -> dict:
    """大模型生成：试卷难度评析、知识点补充、强化建议、鼓励语"""
    context = build_paper_context(analysis, questions_meta, class_type, videos, personal=personal)
    call = student_call(student)
    if personal:
        user_msg = f"""请基于以下学情数据输出 JSON（严格按此结构）：
{{
  "paper_comment": "试卷整体分析（约350字，客观陈述不带人名和'你'等称呼；语气委婉鼓励；高分侧重表扬与保持，低分侧重下一步计划与进步空间；分析整体难度、板块强弱、主要提升点与复习方向。本次分析无分数，按做对/做错题数评估掌握情况）",
  "section_importance": "各板块在高考中的占比与重要性说明（150字内）",
  "knowledge_supplement": [{{"qid": "题号", "knowledge_point": "规范知识点名称"}}],
  "study_advice": "后续学习建议（约150字，围绕完成直播课、观看知识视频展开，分点给出可执行步骤）",
  "encouragement": "一段真诚温暖的鼓励（约100字，以「{call}」开头，高分表扬成绩、低分强调计划与进步）"
}}
学情数据：
{context}"""
    else:
        user_msg = f"""请基于以下学情数据输出 JSON（严格按此结构）：
{{
  "paper_comment": "试卷整体分析（约350字，客观陈述不带人名和'你'等称呼；语气委婉鼓励；高分侧重表扬与保持，低分侧重下一步计划与进步空间；分析整体难度、板块强弱、选择题/非选择题表现、主要提升点与复习方向）",
  "section_importance": "各板块在高考中的占比与重要性说明（150字内）",
  "knowledge_supplement": [{{"qid": "题号", "knowledge_point": "规范知识点名称"}}],
  "study_advice": "后续学习建议（约150字，围绕完成直播课、观看知识视频展开，分点给出可执行步骤）",
  "encouragement": "一段真诚温暖的鼓励（约100字，以「{call}」开头，高分表扬成绩、低分强调计划与进步）"
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


def suggest_knowledge_llm(questions: list, timeout: int = 300) -> list:
    """调用大模型为题目匹配大纲知识点（优先使用；失败抛异常由调用方回退本地规则）。
    questions: [{qid, text}]；返回 [{qid, section_key, knowledge_point}]。
    """
    from .knowledge import load_outline
    outline = load_outline()
    kp_lines = []
    for sec in outline.get("sections", []):
        for kp in sec.get("knowledge_points", []):
            kp_lines.append(f"{kp['name']}（{sec['name']}）")
    kp_text = "、".join(kp_lines)
    q_lines = "\n".join(f"{i + 1}. 题号[{q.get('qid', '?')}]：{(q.get('text') or '')[:300]}" for i, q in enumerate(questions))
    system = "你是资深高考物理教师。请根据每道题的题目内容，从给定的大纲知识点中选出最匹配的一个（只能从列表中选择，不能自创）。不确定的题目可以跳过。只输出 JSON。"
    user = f"""大纲知识点（板块）：{kp_text}

题目列表：
{q_lines}

请输出 JSON：{{"suggestions": [{{"qid": "题号", "knowledge_point": "知识点名"}}]}}"""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    data = chat_json(messages, temperature=0.1, timeout=timeout)
    # 规范化：知识点名 → 板块 key
    name_to_sec = {}
    for sec in outline.get("sections", []):
        for kp in sec.get("knowledge_points", []):
            name_to_sec[kp["name"]] = sec["key"]
    result = []
    for s in data.get("suggestions") or []:
        kp = (s.get("knowledge_point") or "").strip()
        if not kp:
            continue
        # 尽量匹配到大纲内的标准名称（容错：包含匹配）
        exact = name_to_sec.get(kp)
        if exact:
            result.append({"qid": str(s.get("qid", "")), "section_key": exact, "knowledge_point": kp})
        else:
            for name, sec_key in name_to_sec.items():
                if kp in name or name in kp:
                    result.append({"qid": str(s.get("qid", "")), "section_key": sec_key, "knowledge_point": name})
                    break
    return result


def template_advice(analysis: dict, student: str = "", personal: bool = False) -> dict:
    """纯规则模式的模板化建议文案（不依赖网络）。委婉分层：高分表扬，低分强调下一步计划。
    personal=True：无分数模式（个人分析），按做对/做错题数与正确率描述。"""
    sec = analysis["sections"]
    total = analysis["total_got"]
    full = analysis["total_full"]
    rate = analysis["overall_rate"]
    choice_rate = analysis.get("choice_rate", 0)
    non_rate = analysis.get("nonchoice_rate", 0)
    call = student_call(student)

    # ---- 整体分析（~350字，客观不带称呼） ----
    pts = []
    if personal:
        wrong_n = analysis.get("total_lost", 0)
        if rate >= 0.85:
            pts.append(f"本次试卷共{full:g}道题，做对{total:g}道、做错{wrong_n:g}道，正确率{rate:.0%}，整体掌握情况相当出色。")
        elif rate >= 0.6:
            pts.append(f"本次试卷共{full:g}道题，做对{total:g}道、做错{wrong_n:g}道，正确率{rate:.0%}，整体基础比较扎实。")
        else:
            pts.append(f"本次试卷共{full:g}道题，做对{total:g}道、做错{wrong_n:g}道，正确率{rate:.0%}，还有一定的提升空间。")
        if sec:
            weak = [s for s in sec if s["rate"] < 0.6]
            strong = [s for s in sec if s["rate"] >= 0.7]
            if weak:
                pts.append(f"从板块分布看，{('、'.join(s['name'] for s in weak[:3]))}等板块错题较为集中，这些内容在高考中占比较为可观，值得优先投入时间。")
            if strong:
                pts.append(f"{('、'.join(s['name'] for s in strong[:2]))}等板块掌握得不错，说明基础知识与常规题型训练已有成效。")
        if sec and weak:
            w = weak[0]
            kps = set(q["knowledge_point"] for q in w["loss_questions"] if q.get("knowledge_point"))
            if kps:
                pts.append(f"建议围绕{('、'.join(list(kps)[:3]))}等知识点，结合对应知识视频做针对性巩固，再通过同类题检验效果。")
        pts.append("总体来看，按部就班地完成计划，成绩稳步提升是完全可以期待的。")
    else:
        if rate >= 0.85:
            pts.append(f"本次试卷满分{full:g}分，得分{total:g}分，得分率{rate:.0%}，整体表现相当出色。")
        elif rate >= 0.6:
            pts.append(f"本次试卷满分{full:g}分，得分{total:g}分，得分率{rate:.0%}，整体基础比较扎实。")
        else:
            pts.append(f"本次试卷满分{full:g}分，得分{total:g}分，得分率{rate:.0%}，还有一定的提升空间。")
        if sec:
            weak = [s for s in sec if s["rate"] < 0.6]
            strong = [s for s in sec if s["rate"] >= 0.7]
            if weak:
                pts.append(f"从板块分布看，{('、'.join(s['name'] for s in weak[:3]))}等板块可以进一步巩固，这些内容在高考中占比较为可观，值得优先投入时间。")
            if strong:
                pts.append(f"{('、'.join(s['name'] for s in strong[:2]))}等板块掌握得不错，说明基础知识与常规题型训练已有成效。")
        pts.append(f"从题型结构看，选择题得分率{choice_rate:.0%}，非选择题得分率{non_rate:.0%}，非选择题（实验题与计算题）方面可以继续加强解题步骤的规范性与综合建模能力。")
        if sec and weak:
            w = weak[0]
            kps = set(q["knowledge_point"] for q in w["loss_questions"] if q.get("knowledge_point"))
            if kps:
                pts.append(f"建议围绕{('、'.join(list(kps)[:3]))}等知识点，结合对应知识视频做针对性巩固，再通过同类题检验效果。")
        pts.append("总体来看，按部就班地完成计划，成绩稳步提升是完全可以期待的。")
    paper_comment = "".join(pts)

    # ---- 鼓励（~100字，分层） ----
    if personal:
        if rate >= 0.85:
            encouragement = (
                f"{call}，这次做对了{total:g}道题，正确率{rate:.0%}，非常优秀的掌握情况！这说明你的努力正在开花结果。"
                "保持住这份节奏，把个别错题涉及的小知识点再完善一下，向更高的目标稳步前进。"
                "老师和家长都为你的进步感到高兴，继续加油！"
            )
        elif rate >= 0.6:
            encouragement = (
                f"{call}，这次做对了{total:g}道题，整体表现不错！掌握情况在稳步提升，基础也越来越扎实。"
                "接下来按学习计划把错题涉及的知识点逐个落实，配合直播课和知识视频，"
                "下一次一定能看到更明显的进步。继续加油！"
            )
        else:
            encouragement = (
                f"{call}，这次做错了不少题目，先别灰心——错题只是现在的坐标，并不代表你的上限。"
                "按照下面的学习计划，优先完成直播课，把对应知识视频看一遍，再练习同类题，"
                "进步是可以实实在在实现的。我们一步一步来，一起加油！"
            )
    else:
        if rate >= 0.85:
            encouragement = (
                f"{call}，这次拿到了{total:g}分，非常优秀的成绩！这说明你的努力正在开花结果。"
                "保持住这份节奏，把个别需要巩固的小知识点再完善一下，向更高的目标稳步前进。"
                "老师和家长都为你的进步感到高兴，继续加油！"
            )
        elif rate >= 0.6:
            encouragement = (
                f"{call}，这次获得{total:g}分，整体表现不错！分数在稳步提升，基础也越来越扎实。"
                "接下来按学习计划把需要巩固的知识点逐个落实，配合直播课和知识视频，"
                "下一次一定能看到更明显的进步。继续加油！"
            )
        else:
            encouragement = (
                f"{call}，这次获得{total:g}分，先别灰心——分数只是现在的坐标，并不代表你的上限。"
                "按照下面的学习计划，优先完成直播课，把对应知识视频看一遍，再练习同类题，"
                "进步是可以实实在在实现的。我们一步一步来，一起加油！"
            )

    # ---- 后续建议（围绕直播课、知识视频） ----
    study_advice = (
        "后续建议：① 按本报告的强化学习计划，优先完成对应直播课的学习；"
        "② 每天安排固定时间观看待巩固知识点匹配的知识视频，边看边做笔记；"
        "③ 每学完一个知识点，完成3~5道同类题检验掌握效果；"
        "④ 每周复盘一次，确保同类题型不再失分。"
    )

    return {
        "paper_comment": paper_comment,
        "section_importance": "力学与电磁学在高考物理中合计约占70%的分值，是拉分关键；热学、光学、原子物理以基础概念为主，属于必须拿稳的送分板块；实验题渗透在各板块中，注重原理与数据处理能力。",
        "knowledge_supplement": [],
        "study_advice": study_advice,
        "encouragement": encouragement,
    }
