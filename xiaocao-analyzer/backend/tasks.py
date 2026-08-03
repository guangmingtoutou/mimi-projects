"""任务管理：创建任务、后台线程执行完整分析管线。"""
import logging
import os
import threading
import time
import uuid

from . import downloader, report, scoring, transcribe, vision

logger = logging.getLogger("tasks")

LEVELS = ("speech", "speech_vision", "multimodal")
MODES = ("cloud", "local")

PHASES = {
    "queued": "排队中",
    "preparing": "准备视频",
    "transcribing": "语音识别",
    "vision": "画面分析",
    "scoring": "评分中",
    "done": "已完成",
    "failed": "失败",
}


class TaskManager:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.tasks: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.reports_dir = os.path.join(cfg["app"]["data_dir"], "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

    def create(self, source_type: str, source: str, name: str | None,
               analysis_level: str, run_mode: str) -> dict:
        if analysis_level not in LEVELS:
            raise ValueError(f"analysis_level 必须是 {LEVELS} 之一")
        if run_mode not in MODES:
            raise ValueError(f"run_mode 必须是 {MODES} 之一")

        task_id = uuid.uuid4().hex[:12]
        display = name or (os.path.basename(source) if source_type == "file" else source)
        if len(display) > 60:
            display = display[:57] + "…"
        task = {
            "id": task_id,
            "status": "queued",
            "phase": "queued",
            "progress": 2,
            "message": "排队中…",
            "source_type": source_type,
            "source": source,
            "display_name": display,
            "analysis_level": analysis_level,
            "run_mode": run_mode,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": None,
            "total_score": None,
            "warnings": [],
            "tag": "小灶课",
        }
        with self.lock:
            self.tasks[task_id] = task
        threading.Thread(target=self._run, args=(task_id,), daemon=True).start()
        return task

    def get(self, task_id: str) -> dict | None:
        with self.lock:
            t = self.tasks.get(task_id)
            return dict(t) if t else None

    def list(self) -> list[dict]:
        with self.lock:
            return [dict(t) for t in sorted(
                self.tasks.values(), key=lambda x: x["created_at"], reverse=True)]

    # ---------- 内部执行 ----------
    def _update(self, task_id: str, **kw):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(kw)

    def _progress(self, task_id: str, message: str, progress: int):
        self._update(task_id, message=message, progress=progress)

    def _run(self, task_id: str):
        task = self.get(task_id)
        cfg = self.cfg
        mock = cfg["app"].get("mock", False)
        video_path = None
        warnings: list[str] = []
        task_dir = os.path.join(cfg["app"]["data_dir"], "tasks", task_id)
        os.makedirs(task_dir, exist_ok=True)
        try:
            # ---- 1. 获取视频 ----
            self._update(task_id, status="running", phase="preparing", progress=5, message="准备视频…")
            if task["source_type"] == "file":
                video_path = task["source"]
            else:
                self._progress(task_id, "下载链接视频…", 6)
                video_path = downloader.download(task["source"], os.path.join(task_dir, "download"))
            self._update(task_id, phase="transcribing", message="语音识别…")

            # ---- 2. 转写（云端缺密钥自动降级本地） ----
            try:
                tr = transcribe.transcribe(video_path, task["run_mode"], cfg,
                                           lambda m, p: self._progress(task_id, m, p))
            except RuntimeError as e:
                if task["run_mode"] == "cloud" and "api_key" in str(e):
                    warnings.append("云端语音转写未配置密钥，已自动改用本地 faster-whisper（首次运行会自动下载模型）")
                    tr = transcribe.transcribe(video_path, "local", cfg,
                                               lambda m, p: self._progress(task_id, m, p))
                else:
                    raise
            self._update(task_id, progress=35, message="语音识别完成")
            if not tr["text"].strip():
                raise RuntimeError("未识别到语音内容，请检查视频是否有清晰人声")

            # ---- 3. 画面分析（按档位；未配置时降级） ----
            vision_notes = None
            if task["analysis_level"] != "speech" and not mock:
                try:
                    self._update(task_id, phase="vision", progress=40, message="抽取画面帧…")
                    dense = task["analysis_level"] == "multimodal"
                    interval = max(3, cfg["vision"]["interval_sec"] // (2 if dense else 1))
                    frames = vision.extract_frames(
                        video_path, os.path.join(task_dir, "frames"), interval,
                        cfg["vision"]["max_frames"] * (2 if dense else 1),
                        lambda m, p: self._progress(task_id, m, p))
                    self._progress(task_id, "画面分析中…", 45)
                    vision_notes = vision.analyze_frames(
                        frames, task["run_mode"], cfg, dense=dense,
                        progress_cb=lambda m, p: self._progress(task_id, m, p))
                except RuntimeError as e:
                    warnings.append(f"画面分析不可用，已降级为仅语音分析：{e}")
            elif task["analysis_level"] != "speech":
                vision_notes = "（演示模式，无真实画面数据）"

            # ---- 4. 评分 ----
            self._update(task_id, phase="scoring", progress=78, message="大模型评分中…")
            result = scoring.score_lecture(tr["text"], vision_notes, task["run_mode"], cfg,
                                           lambda m, p: self._progress(task_id, m, p))
            result["transcript"] = tr["text"]
            result["duration"] = tr["duration"]
            result["engine"] = tr["engine"]
            if vision_notes:
                result["vision_notes"] = vision_notes
            result["warnings"] = warnings

            # ---- 5. 报告 ----
            self._progress(task_id, "生成报告…", 92)
            report_dir = os.path.join(self.reports_dir, task_id)
            paths = report.save_report(task, result, report_dir)
            self._update(
                task_id, status="done", phase="done", progress=100,
                message="分析完成" + (f"（{len(warnings)} 条降级提示）" if warnings else ""),
                total_score=result["total"],
                report_html=paths["html"], report_json=paths["json"],
            )
            logger.info("任务 %s 完成，总分 %.1f", task_id, result["total"])
        except Exception as e:
            logger.exception("任务 %s 失败", task_id)
            self._update(task_id, status="failed", phase="failed",
                         message="分析失败", error=str(e), progress=100)
        finally:
            # 上传的视频保留，其他中间文件可清理
            pass
