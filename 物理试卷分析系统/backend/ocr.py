# -*- coding: utf-8 -*-
"""OCR：识别知识视频目录图片（RapidOCR）。未安装时优雅降级。"""
from pathlib import Path

from .knowledge import is_video_title


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa
        return True
    except Exception:
        return False


_ENGINE = None


def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ENGINE = RapidOCR()
        except Exception as e:
            raise RuntimeError(f"OCR 引擎加载失败: {e}")
    return _ENGINE


def ocr_image(path: str | Path) -> list[str]:
    """识别图片文字，返回按行排列的文本列表"""
    if not ocr_available():
        raise RuntimeError("未安装 rapidocr-onnxruntime，无法进行 OCR。请先执行: pip install rapidocr-onnxruntime")
    engine = _get_engine()
    result, _ = engine(str(path))
    if not result:
        return []
    return [item[1] for item in result]


def ocr_video_list(path: str | Path) -> list[dict]:
    """识别视频目录图片 → 视频标题列表（过滤非视频行，去重）
    仅保留形如“1.1.1.1视频标题”的条目，剔除序号、时长、播放量等噪声行。
    """
    lines = ocr_image(path)
    seen = set()
    videos = []
    for line in lines:
        title = line.strip()
        if not is_video_title(title):
            continue
        if title not in seen:
            seen.add(title)
            videos.append({"title": title, "url": ""})
    return videos
