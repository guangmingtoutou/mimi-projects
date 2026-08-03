"""报告生成：HTML 报告 + JSON 原始数据。"""
import html
import json
import os
import time

DIMENSION_LABELS = {
    "correctness": "知识点正确性",
    "completeness": "知识点完整性",
    "example_guidance": "例题思路引导及正确解答",
    "clarity": "讲解清晰度",
    "interactivity": "互动性",
}

LEVEL_LABELS = {
    "speech": "仅语音分析",
    "speech_vision": "语音 + 画面分析",
    "multimodal": "多模态分析",
}

MODE_LABELS = {"cloud": "云服务", "local": "本地运行"}

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>小灶课质量报告 - @@TITLE@@</title>
<style>
  body { font-family: "PingFang SC","Microsoft YaHei",system-ui,sans-serif; margin:0; background:#f7f5f0; color:#2d2a26; }
  .wrap { max-width: 860px; margin: 0 auto; padding: 28px 20px 60px; }
  .head { display:flex; align-items:center; gap:20px; background:linear-gradient(135deg,#ffb347,#f97316);
          color:#fff; border-radius:16px; padding:24px 28px; box-shadow:0 6px 20px rgba(249,115,22,.25); }
  .head .total { font-size:56px; font-weight:800; line-height:1; }
  .head .meta { flex:1; }
  .head h1 { margin:0 0 6px; font-size:20px; }
  .head .sub { font-size:13px; opacity:.92; line-height:1.7; }
  .badge { display:inline-block; background:rgba(255,255,255,.22); border-radius:20px; padding:2px 10px;
           font-size:12px; margin-right:6px; }
  .card { background:#fff; border-radius:14px; padding:20px 24px; margin-top:16px;
          box-shadow:0 2px 8px rgba(0,0,0,.05); }
  .card h2 { margin:0 0 14px; font-size:16px; color:#b45309; border-left:4px solid #f97316; padding-left:10px; }
  .dim { margin-bottom:16px; }
  .dim .row { display:flex; justify-content:space-between; font-size:14px; margin-bottom:6px; }
  .dim .bar { height:10px; background:#f0ece4; border-radius:6px; overflow:hidden; }
  .dim .bar i { display:block; height:100%; border-radius:6px;
                background:linear-gradient(90deg,#fbbf24,#f97316); }
  .dim .reason { font-size:13px; color:#6b6b6b; margin-top:6px; }
  .comment { font-size:15px; line-height:1.9; color:#3d3a35; }
  ul { margin:6px 0; padding-left:20px; }
  li { font-size:14px; line-height:1.8; }
  details { margin-top:12px; }
  summary { cursor:pointer; font-size:14px; color:#b45309; font-weight:600; }
  .transcript { white-space:pre-wrap; font-size:13px; color:#555; line-height:1.8;
                background:#faf8f3; border-radius:10px; padding:14px; max-height:400px; overflow:auto; }
  .foot { text-align:center; color:#aaa; font-size:12px; margin-top:26px; }
  .tag { font-size:12px; color:#fff; background:#f97316; border-radius:4px; padding:1px 6px; margin-left:8px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div class="total">@@TOTAL@@<span style="font-size:20px">/10</span></div>
    <div class="meta">
      <h1>@@TITLE@@ <span class="tag">@@TAG@@</span></h1>
      <div class="sub">
        <span class="badge">@@LEVEL@@</span><span class="badge">@@MODE@@</span>
        <span class="badge">时长 @@DURATION@@</span><span class="badge">@@ENGINE@@</span>
        <div style="margin-top:6px">分析时间：@@TIME@@</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>综合点评（≤200 字）</h2>
    <div class="comment">@@COMMENT@@</div>
  </div>

  <div class="card">
    <h2>分维度评分</h2>
    @@DIMS@@
  </div>

  <div class="card">
    <h2>亮点</h2>
    <ul>@@STRENGTHS@@</ul>
    <h2 style="margin-top:18px">不足</h2>
    <ul>@@WEAKNESSES@@</ul>
    <h2 style="margin-top:18px">改进建议</h2>
    <ul>@@SUGGESTIONS@@</ul>
  </div>

  @@VISION_CARD@@

  <div class="card">
    <h2>课堂转录</h2>
    <details>
      <summary>展开 / 收起全文转录（@@TRANSCRIPT_LEN@@ 字）</summary>
      <div class="transcript">@@TRANSCRIPT@@</div>
    </details>
  </div>

  <div class="foot">由「小灶课质量分析系统」生成 🍯</div>
</div>
</body>
</html>
"""


def _bar(score: float) -> str:
    pct = max(0, min(100, round(score * 10)))
    return f'<div class="bar"><i style="width:{pct}%"></i></div>'


def build_html(task: dict, result: dict) -> str:
    scores = result["scores"]
    dims = []
    for key, label in DIMENSION_LABELS.items():
        item = scores[key]
        dims.append(
            f'<div class="dim"><div class="row"><span>{label}</span>'
            f'<b>{item["score"]:.1f} 分</b></div>{_bar(item["score"])}'
            f'<div class="reason">{html.escape(item["reason"])}</div></div>'
        )
    vision_card = ""
    if result.get("vision_notes"):
        vision_card = (
            '<div class="card"><h2>画面观察</h2>'
            '<div class="comment" style="white-space:pre-wrap">'
            + html.escape(result["vision_notes"][:4000]) + "</div></div>"
        )

    def lis(items):
        return "".join(f"<li>{html.escape(str(x))}</li>" for x in items) or "<li>—</li>"

    return (
        _TEMPLATE
        .replace("@@TITLE@@", html.escape(task.get("display_name", "小灶课")))
        .replace("@@TAG@@", html.escape(task.get("tag", "演示")))
        .replace("@@TOTAL@@", f'{result["total"]:.1f}')
        .replace("@@LEVEL@@", LEVEL_LABELS.get(task["analysis_level"], task["analysis_level"]))
        .replace("@@MODE@@", MODE_LABELS.get(task["run_mode"], task["run_mode"]))
        .replace("@@DURATION@@", f'{result.get("duration", "?")} 秒')
        .replace("@@ENGINE@@", html.escape(result.get("engine", "?")))
        .replace("@@TIME@@", time.strftime("%Y-%m-%d %H:%M:%S"))
        .replace("@@COMMENT@@", html.escape(result["comment"]))
        .replace("@@DIMS@@", "\n".join(dims))
        .replace("@@STRENGTHS@@", lis(result.get("strengths", [])))
        .replace("@@WEAKNESSES@@", lis(result.get("weaknesses", [])))
        .replace("@@SUGGESTIONS@@", lis(result.get("suggestions", [])))
        .replace("@@VISION_CARD@@", vision_card)
        .replace("@@TRANSCRIPT_LEN@@", str(len(result.get("transcript", ""))))
        .replace("@@TRANSCRIPT@@", html.escape(result.get("transcript", "")))
    )


def save_report(task: dict, result: dict, reports_dir: str) -> dict:
    os.makedirs(reports_dir, exist_ok=True)
    html_path = os.path.join(reports_dir, "report.html")
    json_path = os.path.join(reports_dir, "report.json")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(task, result))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"task": task, "result": result}, f, ensure_ascii=False, indent=2)
    return {"html": html_path, "json": json_path}
