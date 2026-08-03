"""小灶课质量分析系统 - FastAPI 入口。

启动:  .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8787
或:    bash run.sh
"""
import logging
import os
import shutil
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config as app_config
from .config import load_config
from .tasks import TaskManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT, "frontend")

cfg = load_config()
os.makedirs(cfg["app"]["data_dir"], exist_ok=True)
manager = TaskManager(cfg)

app = FastAPI(title="小灶课质量分析系统", version="1.0.0")

UPLOAD_DIR = os.path.join(cfg["app"]["data_dir"], "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD = cfg["app"]["max_upload_mb"] * 1024 * 1024


@app.get("/", response_class=HTMLResponse)
def index():
    idx = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(idx):
        return HTMLResponse("<h1>前端文件缺失：frontend/index.html</h1>", status_code=500)
    with open(idx, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/tasks")
async def create_task(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    name: str | None = Form(default=None),
    analysis_level: str = Form(...),
    run_mode: str = Form(...),
):
    """创建分析任务：上传视频 或 提供链接（二选一）。"""
    if file is None and not url:
        raise HTTPException(400, "请上传视频文件或填写视频链接")
    if file is not None and url:
        raise HTTPException(400, "上传文件和链接只能二选一")

    try:
        if file is not None:
            ext = os.path.splitext(file.filename or "")[1].lower() or ".mp4"
            if ext not in (".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm", ".ts", ".m4v", ".wmv"):
                raise HTTPException(400, f"不支持的文件格式：{ext}")
            saved = os.path.join(UPLOAD_DIR, uuid.uuid4().hex + ext)
            size = 0
            with open(saved, "wb") as out:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        out.close()
                        os.remove(saved)
                        raise HTTPException(413, f"文件超过大小限制（{cfg['app']['max_upload_mb']} MB）")
                    out.write(chunk)
            task = manager.create("file", saved, name or file.filename, analysis_level, run_mode)
        else:
            url = url.strip()
            if not url.startswith(("http://", "https://")):
                raise HTTPException(400, "链接格式不正确")
            task = manager.create("url", url, name, analysis_level, run_mode)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"创建任务失败: {e}") from e

    return JSONResponse(task)


@app.get("/api/tasks")
def list_tasks():
    return JSONResponse(manager.list())


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    task = manager.get(task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    return JSONResponse(task)


@app.get("/api/tasks/{task_id}/report")
def get_report(task_id: str):
    task = manager.get(task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    if task.get("status") != "done" or not task.get("report_html"):
        raise HTTPException(409, "报告尚未生成")
    fname = f"小灶课质量报告_{task_id}.html"
    return FileResponse(task["report_html"], media_type="text/html", filename=fname)


@app.get("/api/tasks/{task_id}/report.json")
def get_report_json(task_id: str):
    task = manager.get(task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    if task.get("status") != "done" or not task.get("report_json"):
        raise HTTPException(409, "报告尚未生成")
    return FileResponse(task["report_json"], media_type="application/json",
                        filename=f"report_{task_id}.json")


@app.get("/api/settings")
def get_settings():
    """返回各云服务的配置状态（不返回密钥明文）。"""
    s = {"mock": bool(cfg["app"].get("mock")), "data_dir": cfg["app"]["data_dir"]}
    for section in ("whisper", "vision", "llm"):
        cloud = cfg[section]["cloud"]
        s[f"{section}_cloud"] = {
            "configured": bool(cloud.get("api_key")),
            "api_base": cloud.get("api_base", ""),
            "model": cloud.get("model", ""),
        }
    return JSONResponse(s)


@app.put("/api/settings")
async def put_settings(payload: dict):
    """保存云服务密钥与模型配置，写回 config.yaml（下次分析立即生效）。"""
    mapping = {
        "whisper_api_key": ("whisper", "cloud", "api_key"),
        "whisper_base_url": ("whisper", "cloud", "api_base"),
        "whisper_model": ("whisper", "cloud", "model"),
        "vision_api_key": ("vision", "cloud", "api_key"),
        "vision_base_url": ("vision", "cloud", "api_base"),
        "vision_model": ("vision", "cloud", "model"),
        "llm_api_key": ("llm", "cloud", "api_key"),
        "llm_base_url": ("llm", "cloud", "api_base"),
        "llm_model": ("llm", "cloud", "model"),
    }
    changed = []
    for key, (section, mode, field) in mapping.items():
        if key in payload and payload[key] is not None:
            cfg[section][mode][field] = str(payload[key]).strip()
            changed.append(key)
    try:
        app_config.save_config(cfg)
    except Exception as e:
        raise HTTPException(500, f"配置保存失败: {e}") from e
    return JSONResponse({"ok": True, "updated": changed})


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    import uvicorn

    uvicorn.run(app, host=cfg["app"]["host"], port=cfg["app"]["port"])
