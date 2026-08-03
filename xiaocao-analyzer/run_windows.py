"""Windows 可执行文件入口（PyInstaller 打包 run_windows.py）。

双击 exe 后：生成配置 → 启动服务 → 自动打开浏览器。
关闭黑色控制台窗口即退出服务。
"""
import multiprocessing
import os
import sys
import threading
import time
import webbrowser

PORT = 8787


def _open_browser() -> None:
    time.sleep(2.0)
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    except Exception:
        pass


def main() -> None:
    multiprocessing.freeze_support()

    # 确保配置文件存在（首次运行自动生成）
    from backend import config as app_config
    app_config.ensure_config_file()

    print("=" * 56)
    print("  🍯 小灶课质量分析系统 正在启动…")
    print(f"  地址：http://127.0.0.1:{PORT}")
    print("  浏览器即将自动打开，如未打开请手动访问上述地址")
    print("  关闭本窗口 = 停止服务")
    print("=" * 56)

    from backend.main import app
    import uvicorn

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
