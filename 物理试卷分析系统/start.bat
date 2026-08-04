@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   物理试卷分析系统
echo   正在启动，浏览器将自动打开...
echo   访问地址: http://127.0.0.1:8787
echo   关闭本窗口即停止服务
echo ============================================
REM 优先使用内置 runtime（绿色免安装版），否则用系统 Python
if exist "%~dp0runtime\python.exe" (
  "%~dp0runtime\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
) else (
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
)
pause
