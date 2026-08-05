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
    """HTML → 单张纵向长图（整页内容，超出视口部分自动裁剪空白）。
    方案：用较大视口高度截图，再用 PIL 裁剪底部纯色空白，保证一张图包含全部内容。
    中间文件（*.tall.png）裁剪后立即删除，不残留。
    """
    url = html_path.resolve().as_uri()
    tall = png_path.with_suffix(".tall.png")
    _run_browser([f"--window-size={width},6000", f"--screenshot={tall}", url])
    try:
        _crop_blank(tall, png_path)
    finally:
        tall.unlink(missing_ok=True)
    return png_path


def _crop_blank(src: Path, dst: Path, bg_tolerance: int = 8) -> None:
    """裁剪底部与背景色一致的空白区域（报告背景为 #fffdf9 近白）"""
    try:
        from PIL import Image
    except Exception:
        # 无 PIL 时直接使用原图
        import shutil
        shutil.copy(src, dst)
        return
    img = Image.open(src).convert("RGB")
    w, h = img.size
    # 取左上角像素作为背景色参考
    bg = img.getpixel((min(20, w - 1), min(20, h - 1)))

    def _close(c):
        return all(abs(c[i] - bg[i]) <= bg_tolerance for i in range(3))

    bottom = h
    # 从底部向上找第一个非背景行；空白判定：该行 98% 以上像素接近背景色
    from PIL import ImageChops
    for y in range(h - 1, -1, -1):
        row = [img.getpixel((x, y)) for x in range(0, w, 4)]
        non_bg = sum(1 for c in row if not _close(c))
        if non_bg > max(2, len(row) * 0.02):
            bottom = y + 8  # 留 8px 边距
            break
    img.crop((0, 0, w, min(bottom, h))).save(dst, "PNG")
