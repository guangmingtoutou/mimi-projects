"""LLM 评分：按 5 个维度给课程打分并输出 ≤200 字综合点评。"""
import json
import logging
import re

logger = logging.getLogger("scoring")

DIMENSIONS = {
    "correctness": "知识点正确性：讲授的物理概念、公式、规律是否准确无误",
    "completeness": "知识点完整性：核心知识、条件、适用范围是否讲全，有没有明显遗漏",
    "example_guidance": "例题思路引导及正确解答：例题是否典型、是否有清晰的思路引导、解答是否规范正确",
    "clarity": "讲解清晰度：语言是否清楚有条理、逻辑是否顺畅、重点是否突出、学生是否容易跟上",
    "interactivity": "互动性：是否提问、是否关注学生反馈、课堂是否有互动环节",
}

SYSTEM_PROMPT = (
    "你是一位资深高中物理教研专家，擅长评课。你会收到一节高中物理小灶课的课堂转录文本"
    "（以及可选的画面观察记录）。请从以下 5 个维度评价任课老师的授课质量："
    + "；".join(f"{k}（{v}）" for k, v in DIMENSIONS.items())
    + "。"
    "评分标准：0-10 分，6 分及格，8 分以上为优秀。"
    "请输出严格 JSON（不要包含任何其他文字），格式：\n"
    '{"scores": {"correctness": {"score": 0-10, "reason": "一句话理由"}, '
    '"completeness": {...}, "example_guidance": {...}, "clarity": {...}, "interactivity": {...}}, '
    '"total": 0-10, "comment": "不超过200字的综合点评", '
    '"strengths": ["亮点1", "亮点2"], "weaknesses": ["不足1", "不足2"], '
    '"suggestions": ["改进建议1", "改进建议2"]}'
)

MOCK_RESULT = {
    "scores": {
        "correctness": {"score": 9, "reason": "公式与推导均正确，刹车陷阱处理得当"},
        "completeness": {"score": 8, "reason": "核心推论讲解完整，但未展开图像法"},
        "example_guidance": {"score": 9, "reason": "例题典型，先判断停车时间再代入，思路引导清晰"},
        "clarity": {"score": 8, "reason": "讲解有条理，步骤分明，语速适中"},
        "interactivity": {"score": 6, "reason": "有口头提问但等待学生反馈的时间偏短"},
    },
    "total": 8.0,
    "comment": "本节课围绕匀变速直线运动推论展开，知识准确、例题典型，刹车问题的'先判停再代入'引导非常到位，体现出扎实的教学功底。若能在讲解后多给学生思考留白、并补充图像法对比，互动与完整性会更上一层楼。",
    "strengths": ["例题思路引导层层递进", "刹车陷阱点讲得清楚", "公式推导规范"],
    "weaknesses": ["互动以口头提问为主，留白不足", "未涉及图像法补充"],
    "suggestions": ["提问后等待 3-5 秒再揭晓答案", "补充 v-t 图像对比讲解"],
}


def _call_llm(messages: list[dict], mode: str, cfg: dict) -> str:
    lcfg = cfg["llm"]["local" if mode == "local" else "cloud"]
    if mode == "cloud" and not lcfg.get("api_key"):
        raise RuntimeError("云模式需要配置 llm.cloud.api_key（config.yaml）")
    import httpx

    payload = {
        "model": lcfg["model"],
        "messages": messages,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {lcfg.get('api_key', 'ollama')}"}
    resp = httpx.post(
        lcfg["api_base"].rstrip("/") + "/chat/completions",
        headers=headers, json=payload, timeout=600,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"评分模型调用失败 HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _parse_json(raw: str) -> dict:
    # 去掉可能的 ```json ``` 包裹
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.S)
    if m:
        raw = m.group(1)
    return json.loads(raw)


def _validate(result: dict) -> dict:
    scores = result.get("scores", {})
    for k in DIMENSIONS:
        item = scores.get(k, {})
        item["score"] = max(0.0, min(10.0, float(item.get("score", 0))))
        item["reason"] = str(item.get("reason", ""))
        scores[k] = item
    total = float(result.get("total", 0))
    result["total"] = max(0.0, min(10.0, total))
    result["comment"] = str(result.get("comment", ""))[:220]
    result["strengths"] = list(result.get("strengths", []))[:6]
    result["weaknesses"] = list(result.get("weaknesses", []))[:6]
    result["suggestions"] = list(result.get("suggestions", []))[:6]
    return result


def score_lecture(transcript: str, vision_notes: str | None, mode: str, cfg: dict,
                  progress_cb=None) -> dict:
    if cfg["app"].get("mock"):
        return json.loads(json.dumps(MOCK_RESULT))
    if progress_cb:
        progress_cb("大模型评分中…", 80)

    user = f"【课堂转录文本】\n{transcript[:12000]}\n"
    if vision_notes:
        user += f"\n【画面观察记录】\n{vision_notes[:6000]}\n"
    user += "\n请输出评分 JSON。"

    raw = _call_llm(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        mode, cfg,
    )
    try:
        result = _parse_json(raw)
        return _validate(result)
    except Exception:
        # 重试一次，要求更严格的输出
        logger.warning("评分 JSON 解析失败，重试一次")
        retry = _call_llm(
            [
                {"role": "system", "content": SYSTEM_PROMPT + " 只输出 JSON，不要输出任何其他内容。"},
                {"role": "user", "content": user + "\n请只输出合法 JSON 对象。"},
            ],
            mode, cfg,
        )
        try:
            return _validate(_parse_json(retry))
        except Exception as e:
            raise RuntimeError(f"评分结果解析失败: {e}") from e
