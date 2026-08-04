# -*- coding: utf-8 -*-
"""全局配置：路径、设置读写（data/settings.json）"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CATALOG_DIR = DATA_DIR / "catalogs"
REPORT_DIR = DATA_DIR / "reports"
TMP_DIR = DATA_DIR / "tmp"
STATIC_DIR = BASE_DIR / "backend" / "static"

for d in (DATA_DIR, UPLOAD_DIR, CATALOG_DIR, REPORT_DIR, TMP_DIR):
    d.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "engine_mode": "rule",          # rule | llm | hybrid
    "llm_base_url": "https://api.deepseek.com",
    "llm_api_key": "",
    "llm_model": "deepseek-chat",
    "llm_temperature": 0.7,
    "multi_choice_partial": False,  # 多选题是否部分得分
    "school_name": "",
    "teacher_default": "",
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> dict:
    """保存设置。
    安全约定：llm_api_key 为空字符串时保留旧值（防止前端空表单误清 Key）；
    如需显式清除，请调用 /api/settings/clear-key 接口。
    """
    merged = dict(DEFAULT_SETTINGS)
    merged.update(load_settings())
    for k, v in settings.items():
        if k == "llm_api_key" and not str(v or "").strip():
            continue  # 空 Key 不覆盖旧值
        merged[k] = v
    SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def clear_api_key() -> dict:
    """显式清除 API Key（调用方确认后使用）"""
    merged = load_settings()
    merged["llm_api_key"] = ""
    SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def get_setting(key: str):
    return load_settings().get(key)


# 长图/PDF 导出用的浏览器可执行文件（Edge/Chrome 任选其一）
def find_browser() -> str | None:
    candidates = [
        os.environ.get("PAS_BROWSER", ""),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None
