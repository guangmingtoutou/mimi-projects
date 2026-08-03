"""链接下载：支持直链 mp4 / m3u8 等（走 yt-dlp），腾讯会议链接给出友好提示。"""
import logging
import os
import re
from urllib.parse import urlparse

logger = logging.getLogger("downloader")

# 腾讯会议系域名：回放链接通常需要登录，无法直接抓取
TENCENT_PATTERNS = [
    re.compile(r"(^|\.)meeting\.tencent\.com", re.I),
    re.compile(r"(^|\.)v\.meeting\.tencent\.com", re.I),
    re.compile(r"(^|\.)wemeet\.qq\.com", re.I),
]


def is_tencent_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(p.search(host) for p in TENCENT_PATTERNS)


def download(url: str, out_dir: str) -> str:
    """下载远程视频到 out_dir，返回本地文件路径。"""
    if is_tencent_url(url):
        raise RuntimeError(
            "腾讯会议回放链接需要登录权限，无法直接抓取。\n"
            "请先在腾讯会议客户端/网页端下载录制文件（MP4），再通过「上传视频」提交。"
        )

    os.makedirs(out_dir, exist_ok=True)
    logger.info("开始下载: %s", url)
    try:
        import yt_dlp

        ydl_opts = {
            "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            # 某些格式合并后扩展名不同，做兜底
            if not os.path.exists(path):
                candidates = [os.path.join(out_dir, f) for f in os.listdir(out_dir)]
                candidates = [c for c in candidates if os.path.isfile(c)]
                if candidates:
                    path = max(candidates, key=os.path.getmtime)
            if not os.path.exists(path):
                raise RuntimeError("下载完成但找不到文件")
            logger.info("下载完成: %s", path)
            return path
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"链接下载失败: {e}") from e
