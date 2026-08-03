"""配置加载与保存：优先项目根目录 / exe 旁目录的 config.yaml。

打包（PyInstaller frozen）环境下，数据目录与配置文件都放在 exe 所在目录，
保证用户双击后数据落在看得见的地方。
"""
import os
import sys
import yaml

DEFAULTS = {
    "app": {
        "host": "127.0.0.1",
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


def app_dir() -> str:
    """应用根目录：frozen 时是 exe 所在目录，否则是项目根。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config_path() -> str:
    return os.path.join(app_dir(), "config.yaml")


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | None = None) -> dict:
    path = path or config_path()
    cfg = _deep_merge(DEFAULTS, {})
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
            cfg = _deep_merge(cfg, user_cfg)
        except Exception:
            pass
    if getattr(sys, "frozen", False):
        cfg["app"]["data_dir"] = os.path.join(app_dir(), "data")
    return cfg


def ensure_config_file() -> str:
    """首次运行生成 config.yaml（不含密钥，密钥通过网页设置页写入）。"""
    path = config_path()
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(DEFAULTS, f, allow_unicode=True, sort_keys=False)
    return path


def save_config(cfg: dict) -> None:
    """把当前配置写回 config.yaml。"""
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
