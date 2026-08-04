# -*- coding: utf-8 -*-
"""导出器：HTML 报告 → PDF / 单张长图（本机 Edge/Chrome 无头模式）
关键：每次导出使用独立的临时 user-data-dir，避免与已运行的浏览器实例共用配置导致挂起。"""
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .config import find_browser

BASE_FLAGS = [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--no-first-run",
    "--disable-extensions",
    "--disable-background-networking",
    "--hide-scrollbars",
    "--force-device-scale-factor=1",
]


def _browser() -> str:
    b = find_browser()
    if not b:
        raise RuntimeError("未找到 Edge/Chrome 浏览器，无法导出。请安装 Microsoft Edge 或设置 PAS_BROWSER 环境变量。")
    return b


def _run_browser(args: list, timeout: int = 90) -> None:
    """带独立 user-data-dir 运行无头浏览器"""
    browser = _browser()
    profile = Path(tempfile.gettempdir()) / f"pas_browser_{uuid.uuid4().hex[:10]}"
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [browser, *BASE_FLAGS, f"--user-data-dir={profile}", *args]
    try:
        # 用 DEVNULL 而非管道：Edge 子进程会继承管道句柄导致 run() 永远等待
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    finally:
        # 确保相关进程退出（Windows 下偶有残留）
        try:
            shutil.rmtree(profile, ignore_errors=True)
        except Exception:
            pass


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """HTML → PDF"""
    url = html_path.resolve().as_uri()
    _run_browser([f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header", url])
    return pdf_path


def html_to_long_image(html_path: Path, png_path: Path, width: int = 1000) -> Path:
    """HTML → 单张长图（整页截图）"""
    url = html_path.resolve().as_uri()
    _run_browser([f"--window-size={width},1200", f"--screenshot={png_path}", url])
    return png_path
