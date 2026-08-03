# 🍯 小灶课质量分析系统

根据小灶课视频，自动分析**老师授课质量**：语音转写 + 画面识别 + 大模型多维度评分，
每节课产出一份 HTML 报告（打分 + ≤200 字综合点评）。

> 目标场景：高中物理小灶课（30 分钟左右），分析对象是**老师**。

## ✨ 功能

- 📼 **两种输入**：本地上传 MP4 / 粘贴视频直链（m3u8 等）
- 🎚️ **三档分析深度**：
  - `仅语音分析` — 转写课堂语音，只评讲得对不对、全不全、清不清楚
  - `语音 + 画面` — 额外识别板书 / PPT / 老师教学状态
  - `多模态分析` — 高密度采样画面 + 语音，深度分析课堂节奏与师生互动
- ☁️💻 **两种运行方式**：云服务（快、准，需 API key）/ 本地跑（免费、隐私，需装模型）
- 📊 **5 个评分维度**：知识点正确性 · 完整性 · 例题思路引导及正确解答 · 讲解清晰度 · 互动性
- 📄 **每课一份报告**：总分 + 分维度得分及理由 + 亮点/不足/建议 + ≤200 字综合点评 + 全文转录
- 🖥️ **网页操作**：上传、提交、进度查看、一键下载报告

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.10+）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 配置（云服务模式需要填密钥）
cp config.yaml.example config.yaml
#    编辑 config.yaml：
#    - llm.cloud.api_key   评分大模型密钥（DeepSeek / 通义 / OpenAI 均可）
#    - whisper.cloud       语音转写密钥（可选，本地模式不需要）
#    - vision.cloud        画面分析密钥（语音+画面 / 多模态档需要）

# 3. 启动
bash run.sh
# 浏览器打开 http://localhost:8787
```

### 演示模式（无密钥也能玩）

```yaml
# config.yaml
app:
  mock: true   # 不调用真实模型，用示例数据跑通全流程
```

## ⚙️ 运行方式说明

| | ☁️ 云服务 | 💻 本地运行 |
|---|---|---|
| 语音转写 | OpenAI 兼容 `/audio/transcriptions`（OpenAI / Groq / 阿里云百炼） | [faster-whisper](https://github.com/SYSTRAN/faster-whisper)（默认 medium 模型，首次运行自动下载） |
| 画面分析 | 视觉大模型（qwen-vl-max / GPT-4o 等） | Ollama 视觉模型（qwen2.5vl / llava，需先 `ollama pull`） |
| 评分 | 任意 OpenAI 兼容大模型（推荐 DeepSeek / 通义） | Ollama（推荐 qwen2.5:14b 及以上） |

本地模式首次使用：

```bash
# 安装 Ollama 并拉取模型
ollama pull qwen2.5:14b      # 评分
ollama pull qwen2.5vl        # 画面分析（可选）
```

## 🔗 关于腾讯会议链接

腾讯会议**回放链接**需要登录权限，无法直接抓取。
请在腾讯会议客户端「录制」中下载 MP4 后，再通过网页上传。
本系统支持粘贴**直链**（.mp4 / .m3u8 等）由 yt-dlp 自动下载。

## 📁 项目结构

```
xiaocao-analyzer/
├── backend/
│   ├── main.py         # FastAPI 入口与路由
│   ├── tasks.py        # 任务调度（后台线程全流程）
│   ├── transcribe.py   # 语音转写（本地/云端）
│   ├── vision.py       # 画面抽帧 + 视觉分析
│   ├── scoring.py      # 大模型五维评分
│   ├── report.py       # HTML/JSON 报告生成
│   ├── downloader.py   # 链接下载
│   └── config.py       # 配置加载
├── frontend/index.html # 单页网页
├── config.yaml.example # 配置模板
└── data/               # 运行时数据（上传/音频/帧/报告）
```

## 🛠️ API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/tasks` | 创建任务（multipart：file 或 url + analysis_level + run_mode） |
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/tasks/{id}` | 任务状态 |
| GET | `/api/tasks/{id}/report` | 下载 HTML 报告 |
| GET | `/api/tasks/{id}/report.json` | 下载 JSON 原始数据 |

---

_由咪咪 🍯 为哈吉蜂制作_
