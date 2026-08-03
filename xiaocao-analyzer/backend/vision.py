"""画面分析：ffmpeg 抽帧 + 视觉大模型（本地 Ollama / 云端 OpenAI 兼容）。"""
import base64
import json
import logging
import os
import subprocess

import imageio_ffmpeg

logger = logging.getLogger("vision")

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

FRAME_QUESTION = (
    "这是高中物理小灶课的视频画面。请仔细观察，回答：\n"
    "1) 画面里出现了什么教学内容？（板书/PPT/公式/例题文字，尽量原样转录关键内容）\n"
    "2) 老师正在做什么？（讲解、书写板书、操作演示、提问等）\n"
    "3) 有没有学生互动迹象？（举手、回答、讨论、出镜）\n"
    "4) 画面清晰度/录制质量如何？\n"
    "用简洁中文分点回答，看不到内容就写'画面不可辨'。"
)

MOCK_VISION = (
    "画面观察（演示数据）：\n"
    "- 板书区可见匀变速直线运动公式：v=v0+at、x=v0t+½at²、v²-v0²=2ax；\n"
    "- 老师在白板上逐步推导刹车例题，写下了'停车时间 t=v0/a=4s'；\n"
    "- 课堂中老师两次提问'大家听懂了吗'，画面未见学生出镜；\n"
    "- 录制画面清晰，板书可辨认。"
)


def extract_frames(video_path: str, out_dir: str, interval_sec: int,
                   max_frames: int, progress_cb=None) -> list[str]:
    """均匀抽帧，返回帧文件路径列表（已按需抽样）。"""
    os.makedirs(out_dir, exist_ok=True)
    # 清空旧帧
    for f in os.listdir(out_dir):
        try:
            os.remove(os.path.join(out_dir, f))
        except OSError:
            pass
    if progress_cb:
        progress_cb("抽取视频画面帧…", 40)
    cmd = [
        FFMPEG, "-y", "-i", video_path,
        "-vf", f"fps=1/{interval_sec},scale=720:-2",
        "-q:v", "3", os.path.join(out_dir, "frame_%04d.jpg"),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"抽帧失败: {r.stderr[-300:] if r.stderr else '未知错误'}")
    frames = sorted(
        os.path.join(out_dir, f) for f in os.listdir(out_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    )
    if not frames:
        raise RuntimeError("未能从视频中抽取任何画面帧")
    # 若帧数超限，均匀抽样
    if len(frames) > max_frames:
        step = len(frames) / max_frames
        frames = [frames[int(i * step)] for i in range(max_frames)]
    logger.info("抽帧 %d 张", len(frames))
    return frames


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _call_vlm(frames: list[str], question: str, mode: str, cfg: dict) -> str:
    vcfg = cfg["vision"]["local" if mode == "local" else "cloud"]
    if mode == "cloud" and not vcfg.get("api_key"):
        raise RuntimeError("云模式需要配置 vision.cloud.api_key（config.yaml）")
    import httpx

    content = [{"type": "text", "text": question}]
    for fp in frames:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{_encode_image(fp)}"},
        })
    payload = {
        "model": vcfg["model"],
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1500,
    }
    headers = {"Authorization": f"Bearer {vcfg.get('api_key', 'ollama')}"}
    resp = httpx.post(
        vcfg["api_base"].rstrip("/") + "/chat/completions",
        headers=headers, json=payload, timeout=600,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"视觉模型调用失败 HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def analyze_frames(frames: list[str], mode: str, cfg: dict,
                   dense: bool = False, progress_cb=None) -> str:
    """对帧分批做视觉描述，返回汇总文本。dense=True 表示多模态档（更细）。"""
    if cfg["app"].get("mock"):
        return MOCK_VISION
    batch_size = 4 if dense else 6
    notes = []
    total = len(frames)
    for i in range(0, total, batch_size):
        batch = frames[i:i + batch_size]
        if progress_cb:
            progress_cb(f"画面分析中（第 {i // batch_size + 1} 批 / 共 {(total + batch_size - 1) // batch_size} 批）…", 45)
        q = FRAME_QUESTION
        if dense:
            q += "\n另外请额外关注：教师语言与画面的配合、课堂节奏变化、是否存在冷场或长时间沉默。"
        try:
            notes.append(_call_vlm(batch, q, mode, cfg))
        except Exception as e:
            notes.append(f"[本批画面分析失败: {e}]")
    return "\n\n".join(notes)
