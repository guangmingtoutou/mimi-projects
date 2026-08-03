"""语音转写：本地 faster-whisper / 云端 OpenAI 兼容接口 / mock 演示。"""
import json
import logging
import os
import subprocess

import imageio_ffmpeg

logger = logging.getLogger("transcribe")

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

MOCK_TRANSCRIPT = (
    "同学们好，今天小灶课我们讲匀变速直线运动的推论。"
    "首先回顾三个基本公式：速度公式、位移公式，还有速度位移关系式。"
    "来看这道例题：一辆汽车刹车，初速度二十米每秒，加速度大小五米每二次方秒，"
    "问刹车后六秒内的位移是多少。注意，这里有个陷阱，刹车问题要先判断停车时间。"
    "我带着大家一步一步推。第一步，求停车时间，二十除以五等于四秒，"
    "所以六秒内的位移实际上就是四秒内的位移。代入公式，位移等于初速度乘时间，"
    "加上二分之一加速度乘时间的平方，算出来是四十米。大家听懂了吗？"
    "这里容易错的地方是直接代入六秒，那就错了。好，这道题就讲到这里。"
)


def extract_audio(video_path: str, audio_path: str, progress_cb=None) -> None:
    """用 ffmpeg 提取 16kHz 单声道 wav。"""
    if progress_cb:
        progress_cb("正在提取音频…", 12)
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    cmd = [
        FFMPEG, "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", audio_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(audio_path):
        raise RuntimeError(f"音频提取失败: {r.stderr[-500:] if r.stderr else '未知错误'}")
    logger.info("音频已提取: %s", audio_path)


def _transcribe_local(audio_path: str, cfg: dict, progress_cb=None) -> dict:
    from faster_whisper import WhisperModel

    wcfg = cfg["whisper"]["local"]
    if progress_cb:
        progress_cb(f"加载本地语音模型 {wcfg['model_size']}…", 20)
    model = WhisperModel(wcfg["model_size"], device=wcfg.get("device", "cpu"), compute_type="int8")
    if progress_cb:
        progress_cb("语音识别中…", 30)
    segments, info = model.transcribe(audio_path, language="zh", vad_filter=True)
    seg_list = []
    text_parts = []
    for seg in segments:
        seg_list.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        text_parts.append(seg.text.strip())
    return {
        "text": "\n".join(text_parts),
        "segments": seg_list,
        "duration": round(info.duration, 1),
        "engine": f"faster-whisper/{wcfg['model_size']}",
    }


def _transcribe_cloud(audio_path: str, cfg: dict, progress_cb=None) -> dict:
    import httpx

    wcfg = cfg["whisper"]["cloud"]
    if not wcfg.get("api_key"):
        raise RuntimeError("云模式需要配置 whisper.cloud.api_key（config.yaml）")
    if progress_cb:
        progress_cb("云端语音识别中…", 30)
    url = wcfg["api_base"].rstrip("/") + "/audio/transcriptions"
    with open(audio_path, "rb") as f:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {wcfg['api_key']}"},
            data={"model": wcfg["model"], "language": "zh", "response_format": "verbose_json"},
            files={"file": (os.path.basename(audio_path), f, "audio/wav")},
            timeout=600,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"云端转写失败 HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    seg_list = []
    for seg in data.get("segments", []):
        seg_list.append({
            "start": round(seg.get("start", 0), 2),
            "end": round(seg.get("end", 0), 2),
            "text": seg.get("text", "").strip(),
        })
    return {
        "text": data.get("text", "").strip(),
        "segments": seg_list,
        "duration": round(data.get("duration", 0), 1),
        "engine": f"cloud/{wcfg['model']}",
    }


def transcribe(video_path: str, mode: str, cfg: dict, progress_cb=None) -> dict:
    """mode: 'local' 或 'cloud'。返回 dict: text/segments/duration/engine。"""
    data_dir = cfg["app"]["data_dir"]
    audio_dir = os.path.join(data_dir, "audio")
    audio_path = os.path.join(audio_dir, os.path.basename(video_path) + ".wav")

    if cfg["app"].get("mock"):
        return {
            "text": MOCK_TRANSCRIPT,
            "segments": [{"start": 0, "end": 0, "text": MOCK_TRANSCRIPT}],
            "duration": 300,
            "engine": "mock",
        }

    extract_audio(video_path, audio_path, progress_cb)
    if mode == "local":
        return _transcribe_local(audio_path, cfg, progress_cb)
    return _transcribe_cloud(audio_path, cfg, progress_cb)
