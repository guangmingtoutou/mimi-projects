#!/usr/bin/env bash
# 小灶课质量分析系统 - 启动脚本
set -e
cd "$(dirname "$0")"

if [ ! -f config.yaml ]; then
  echo "⚠️  未找到 config.yaml，已复制模板（请按需填写云服务密钥）"
  cp config.yaml.example config.yaml
fi

exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8787}"
