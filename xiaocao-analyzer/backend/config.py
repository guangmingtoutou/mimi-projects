"""配置加载：优先读取项目根目录 config.yaml，否则用内置默认值。"""
import os
import yaml

DEFAULTS = {
    "app": {
        "host": "0.0.0.0",
        "port": 8787,
        "data_dir": "data",
        "max_upload_mb": 2048,
        "mock": False,
    },
    "whisper": {
        "local": {"model_size": "medium", "device": "cpu"},
        "cloud": {"api_base": "https://api.openai.com/v1", "api_key": "", "model": "whisper-1"},
    },
    "vision": {
        "interval_sec": 15,
        "max_frames": 40,
        "local": {"api_base": "http://localhost:11434/v1", "model": "qwen2.5vl"},
        "cloud": {"api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "", "model": "qwen-vl-max"},
    },
    "llm": {
        "local": {"api_base": "http://localhost:11434/v1", "model": "qwen2.5:14b"},
        "cloud": {"api_base": "https://api.deepseek.com/v1", "api_key": "", "model": "deepseek-chat"},
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | None = None) -> dict:
    if path is None:
        # 项目根目录（backend/ 的上一级）
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "config.yaml")
    cfg = _deep_merge(DEFAULTS, {})
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, user_cfg)
    return cfg
