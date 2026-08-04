# 物理试卷分析系统

高中物理试卷学情分析工具（本机网页服务）。上传试卷与答题数据，自动生成学生个人/班级批量分析报告，支持导出 PDF / 长图。

## 快速开始

**源码版**（需要 Python 3.10+）：

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
```

浏览器打开 <http://127.0.0.1:8787>

**绿色免安装版**：下载 Release 中的 `物理试卷分析系统_绿色免安装版.zip`，解压后双击 `start.bat` 即可（内置 Python 运行时，无需安装任何环境）。

> 导出 PDF / 长图依赖本机 Microsoft Edge 或 Chrome（Windows 10/11 自带 Edge）。

## 功能

- **个人试卷分析**：上传试卷（图片/PDF/Word）→ 配置题目（题型/板块/分值/得分）→ 生成图文报告（整体难度、板块丢分、强化学习计划、鼓励建议）→ 导出 PDF / 长图
- **批量试卷分析**：上传 xlsx 答题数据（兼容飞书/企业微信表单，含"正确答案"行）→ 自动识别题目与分值 → 按老师一键生成全班报告（含排名）→ zip 打包下载
- **自动判分**：单选字母匹配、多选全对/部分分/顺序无关、主观题选项字母优先
- **知识视频目录**：上传目录截图，OCR 自动识别视频标题（目标班/菁英班两套），错题知识点自动匹配视频
- **大模型模式**：可选填 DeepSeek API Key，生成更专业的学情分析文案（纯规则模板免费离线可用）

## 目录结构

```
├── backend/               # FastAPI 后端
│   ├── main.py            # 接口路由
│   ├── analyzer.py        # 判分与统计引擎
│   ├── knowledge.py       # 高考物理知识体系 + 视频匹配
│   ├── llm.py             # DeepSeek 大模型调用
│   ├── ocr.py             # 目录截图 OCR
│   ├── paper_parser.py    # 试卷文本提取/题目切分
│   ├── report_builder.py  # HTML 报告 + matplotlib 图表
│   ├── exporters.py       # HTML → PDF / 长图
│   ├── batch.py           # xlsx 解析与批量分析
│   └── static/            # 前端页面
├── data/                  # 运行数据（上传/报告/配置）
├── tests/                 # 单元测试
├── start.bat              # Windows 一键启动
└── requirements.txt
```

## 测试

```bash
python -m unittest discover -s tests -v
```

## 安全说明

- 服务仅绑定 `127.0.0.1`，数据全部保存在本机 `data/` 目录，不上传任何服务器
- **发布/分发前请确认 `data/settings.json` 中 `llm_api_key` 为空**（设置页可一键清除），避免 API Key 随包泄露
