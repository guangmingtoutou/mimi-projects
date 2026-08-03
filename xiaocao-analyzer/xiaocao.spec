# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：生成 Windows 单文件 exe（onefile）
# 构建命令：pyinstaller xiaocao.spec --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# 收集带数据/二进制文件的依赖
datas = []
binaries = []
hiddenimports = []

for pkg in ("faster_whisper", "ctranslate2", "av", "onnxruntime", "tokenizers", "huggingface_hub"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

datas += collect_data_files("imageio_ffmpeg")   # ffmpeg 可执行文件
datas += collect_data_files("yt_dlp")            # yt-dlp 版本/插件数据
hiddenimports += collect_submodules("uvicorn")
hiddenimports += ["multipart", "multipart.multipart", "anyio._backends._asyncio"]

a = Analysis(
    ["run_windows.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PySide2", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="小灶课分析",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # 保留控制台窗口显示日志，关闭即退出
    disable_windowed_traceback=False,
)
