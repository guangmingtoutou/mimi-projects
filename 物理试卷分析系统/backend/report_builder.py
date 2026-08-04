# -*- coding: utf-8 -*-
"""报告构建：生成图文精美的 HTML 报告（个人版 / 批量版），内嵌 matplotlib 图表"""
import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from .config import TMP_DIR
from .knowledge import SECTION_INDEX

# 中文字体
for _f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
    if Path(_f).exists():
        font_manager.fontManager.addfont(_f)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

PALETTE = ["#3B6FD4", "#E8590C", "#12B886", "#F59F00", "#7048E8", "#1098AD", "#E64980", "#5C7CFA"]
PALETTE_HEX = ["3B6FD4", "E8590C", "12B886", "F59F00", "7048E8", "1098AD", "E64980", "5C7CFA"]

CSS = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #f4f6fb; color: #2b3445; }
  .page { max-width: 900px; margin: 0 auto; background: #fff; padding: 48px 52px; }
  .header { text-align: center; padding-bottom: 26px; border-bottom: 3px solid #3B6FD4; margin-bottom: 30px; }
  .header .title { font-size: 26px; font-weight: 700; color: #1f3a7a; letter-spacing: 2px; }
  .header .sub { margin-top: 10px; font-size: 14px; color: #667; }
  .header .meta { margin-top: 14px; font-size: 13px; color: #556; }
  .header .meta span { margin: 0 14px; }
  .badge { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 12px; color: #fff; }
  .badge-easy { background: #12B886; } .badge-mid { background: #F59F00; }
  .badge-hard { background: #E8590C; } .badge-vhard { background: #E03131; }
  h2 { font-size: 18px; color: #1f3a7a; margin: 32px 0 14px; padding-left: 12px; border-left: 4px solid #3B6FD4; }
  .cards { display: flex; gap: 14px; flex-wrap: wrap; }
  .card { flex: 1; min-width: 170px; background: linear-gradient(135deg,#3B6FD4,#5C7CFA); color: #fff;
          border-radius: 12px; padding: 16px 18px; }
  .card .v { font-size: 24px; font-weight: 700; }
  .card .k { font-size: 12px; opacity: .85; margin-top: 4px; }
  .card.green { background: linear-gradient(135deg,#12B886,#38D9A9); }
  .card.orange { background: linear-gradient(135deg,#E8590C,#F59F00); }
  .card.gray { background: linear-gradient(135deg,#495057,#868E96); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 10px 0; }
  th, td { border: 1px solid #e3e8f0; padding: 8px 10px; text-align: center; }
  th { background: #eef2fb; color: #1f3a7a; font-weight: 600; }
  tr:nth-child(even) td { background: #fafbfe; }
  .right { color: #12B886; font-weight: 600; } .wrong { color: #E03131; font-weight: 600; }
  .note { font-size: 13px; color: #667; line-height: 1.8; background: #f8f9fc; border-radius: 8px; padding: 14px 18px; }
  .plan-item { display: flex; gap: 12px; padding: 12px 14px; border: 1px solid #e3e8f0; border-radius: 10px; margin: 8px 0; }
  .plan-item .dot { width: 8px; height: 8px; border-radius: 50%; background: #E8590C; margin-top: 6px; flex-shrink: 0; }
  .plan-item .kp { font-weight: 600; color: #1f3a7a; }
  .video-tag { display: inline-block; background: #eef2fb; color: #3B6FD4; border-radius: 6px; padding: 2px 8px;
               font-size: 12px; margin: 2px 4px 2px 0; }
  .footer { margin-top: 40px; padding-top: 16px; border-top: 1px dashed #ccd; text-align: center;
            font-size: 12px; color: #99a; }
  .chart { text-align: center; margin: 10px 0; }
  .chart img { max-width: 100%; }
  .encourage { background: linear-gradient(135deg,#fff4e6,#fff9f0); border: 1px solid #ffd8a8; border-radius: 12px;
               padding: 18px 22px; font-size: 14px; line-height: 2; color: #5c3a12; }
  .section-head { display: inline-block; background: #3B6FD4; color: #fff; border-radius: 6px; padding: 2px 10px; font-size: 13px; }
</style>
"""


def _b64(img_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(img_bytes).decode()


def _chart_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def chart_section_donut(analysis: dict) -> str:
    """板块得分占比环形图（全零时安全降级）"""
    secs = analysis["sections"]
    if not secs:
        return ""
    fig, ax = plt.subplots(figsize=(7.4, 3.6), dpi=160)
    names = [s["name"] for s in secs]
    got = [s["got_score"] for s in secs]
    lost = [s["lost_score"] for s in secs]
    if sum(got) > 0:
        ax.pie(got, labels=names, colors=PALETTE[:len(names)], startangle=90, counterclock=False,
               wedgeprops=dict(width=0.38, edgecolor="white"), autopct="")
    if sum(lost) > 0:
        ax.pie(lost, colors=["#E9ECEF"] * len(lost), startangle=90, counterclock=False,
               wedgeprops=dict(width=0.38, edgecolor="white"), radius=0.62)
    elif sum(got) == 0:
        ax.pie([1], colors=["#E9ECEF"], startangle=90, counterclock=False,
               wedgeprops=dict(width=0.38, edgecolor="white"), radius=0.62)
    ax.text(0, 0.12, f"{analysis['total_got']:.0f}", ha="center", fontsize=20, fontweight="bold", color="#1f3a7a")
    ax.text(0, -0.18, "得分", ha="center", fontsize=11, color="#667")
    ax.set_title("各板块得分占比（外环=得分，内环=丢分）", fontsize=12, color="#1f3a7a")
    return _b64(_chart_bytes(fig))


def chart_qtype_bar(analysis: dict) -> str:
    """题型得分率条形图"""
    qts = analysis["qtypes"]
    if not qts:
        return ""
    fig, ax = plt.subplots(figsize=(7.4, 2.6), dpi=160)
    names = [t["name"] for t in qts]
    rates = [t["rate"] * 100 for t in qts]
    colors = ["#12B886" if r >= 60 else "#F59F00" if r >= 40 else "#E8590C" for r in rates]
    bars = ax.bar(names, rates, color=colors, width=0.55)
    ax.axhline(60, color="#adb5bd", ls="--", lw=1)
    ax.set_ylim(0, 105)
    ax.set_ylabel("得分率 %")
    for b, r in zip(bars, rates):
        ax.text(b.get_x() + b.get_width() / 2, r + 2, f"{r:.0f}%", ha="center", fontsize=10)
    ax.set_title("各题型得分率", fontsize=12, color="#1f3a7a")
    return _b64(_chart_bytes(fig))


def chart_question_scores(analysis: dict) -> str:
    """每题得分（按题号）"""
    qs = analysis["per_question"]
    if not qs:
        return ""
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=160)
    qids = [q["qid"] for q in qs]
    got = [q["got_score"] for q in qs]
    full = [q["full_score"] for q in qs]
    x = range(len(qs))
    ax.bar(x, full, color="#E9ECEF", width=0.62, label="满分")
    ax.bar(x, got, color=["#12B886" if g >= f else "#E8590C" for g, f in zip(got, full)], width=0.62, label="得分")
    ax.set_xticks(list(x))
    ax.set_xticklabels(qids, fontsize=9, rotation=0)
    ax.set_ylabel("分数")
    ax.legend(fontsize=9, loc="upper right")
    ax.set_title("各题得分情况", fontsize=12, color="#1f3a7a")
    return _b64(_chart_bytes(fig))


def difficulty_badge(label: str) -> str:
    m = {"容易": "badge-easy", "中等": "badge-mid", "较难": "badge-hard", "困难": "badge-vhard"}
    return f'<span class="badge {m.get(label, "badge-mid")}">{label}</span>'


def build_html(analysis: dict, meta: dict, advice: dict, study_plan: list, mode: str = "individual") -> str:
    """生成完整报告 HTML。meta: 老师/学生/班型/学校等"""
    school = meta.get("school", "")
    title = "个人试卷分析报告" if mode == "individual" else "试卷分析报告"
    sub = f"{school} · 物理学科" if school else "物理学科 · 学情分析报告"

    meta_line = ""
    if mode == "individual":
        meta_line = (f"<div class='meta'><span>老师：{meta.get('teacher', '')}</span>"
                     f"<span>学生：{meta.get('student', '')}</span>"
                     f"<span>班型：{meta.get('class_type', '')}</span>"
                     f"<span>总分：{analysis['total_got']:.0f} / {analysis['total_full']:.0f}</span>"
                     f"<span>整体难度：{difficulty_badge(analysis['overall_difficulty'])}</span></div>")
    else:
        meta_line = (f"<div class='meta'><span>老师：{meta.get('teacher', '')}</span>"
                     f"<span>学生：{meta.get('student', '')}</span>"
                     f"<span>班型：{meta.get('class_type', '')}</span>"
                     f"<span>总分：{analysis['total_got']:.0f} / {analysis['total_full']:.0f}</span>"
                     f"<span>排名：{meta.get('rank', '-')} / {meta.get('total_students', '-')}</span></div>")

    cards = f"""
    <div class="cards">
      <div class="card"><div class="v">{analysis['total_got']:.0f}</div><div class="k">总得分（满分 {analysis['total_full']:.0f}）</div></div>
      <div class="card green"><div class="v">{analysis['overall_rate']:.0%}</div><div class="k">整体得分率</div></div>
      <div class="card orange"><div class="v">{analysis['total_lost']:.0f}</div><div class="k">总丢分</div></div>
      <div class="card gray"><div class="v">{analysis['overall_difficulty']}</div><div class="k">试卷整体难度</div></div>
    </div>"""

    # 1. 整体难度与板块高考占比
    sec_rows = ""
    for s in analysis["sections"]:
        sec_rows += (f"<tr><td><span class='section-head'>{s['name']}</span></td>"
                     f"<td>{s['gaokao_weight']:.0%}</td><td>{s['importance']}</td>"
                     f"<td>{s['got_score']:.0f} / {s['full_score']:.0f}</td>"
                     f"<td>{s['rate']:.0%}</td><td>{s['lost_score']:.0f}</td>"
                     f"<td>{difficulty_badge(s['difficulty'])}</td></tr>")
    part1 = f"""
    <h2>一、试卷整体分析</h2>
    <div class="note">{advice.get('paper_comment', '')}</div>
    <div class="chart">{chart_section_donut(analysis)}</div>
    <table>
      <tr><th>板块</th><th>高考占比</th><th>重要性</th><th>得分</th><th>得分率</th><th>丢分</th><th>难度</th></tr>
      {sec_rows}
    </table>
    <div class="note">{advice.get('section_importance', '')}</div>"""

    # 2. 各板块丢分汇总
    loss_rows = ""
    for s in analysis["sections"]:
        if not s["loss_questions"]:
            continue
        qlist = "、".join(q["qid"] for q in s["loss_questions"])
        kps = set(q["knowledge_point"] for q in s["loss_questions"] if q["knowledge_point"])
        loss_rows += (f"<tr><td>{s['name']}</td><td>{s['lost_score']:.0f}</td>"
                      f"<td>{qlist}</td><td>{'、'.join(kps) if kps else '未标注'}</td></tr>")
    part2 = f"""
    <h2>二、板块丢分汇总</h2>
    <table>
      <tr><th>板块</th><th>丢分</th><th>对应题目</th><th>考察知识点</th></tr>
      {loss_rows or '<tr><td colspan="4">本试卷无丢分题目，表现很棒！</td></tr>'}
    </table>
    <div class="chart">{chart_question_scores(analysis)}</div>"""

    # 3. 强化学习计划
    plan_items = ""
    if study_plan:
        for item in study_plan:
            vids = "".join(f'<span class="video-tag">📺 {v["title"]}</span>' for v in item["videos"]) if item["videos"] else '<span style="color:#99a;font-size:12px">暂无匹配视频（可导入知识视频目录）</span>'
            plan_items += (f'<div class="plan-item"><div class="dot"></div>'
                           f'<div><div class="kp">{item["knowledge_point"]}（{item["section"]}，丢 {item["lost_score"]:.0f} 分）</div>'
                           f'<div style="font-size:12px;color:#667;margin:4px 0">对应题目：{"、".join(q["qid"] for q in item["questions"])}</div>'
                           f'<div>{vids}</div></div></div>')
    else:
        plan_items = '<div class="note">本次考试没有需要强化的丢分知识点，保持当前节奏即可。</div>'
    part3 = f"""
    <h2>三、强化学习计划</h2>
    {plan_items}"""

    # 4. 鼓励与建议
    part4 = f"""
    <h2>四、鼓励与后续建议</h2>
    <div class="encourage">{advice.get('encouragement', '')}</div>
    <div class="note" style="margin-top:12px">{advice.get('study_advice', '')}</div>"""

    # 批量模式附加：逐题作答情况
    extra = ""
    if mode == "batch":
        q_rows = ""
        for q in analysis["per_question"]:
            status = f'<span class="right">正确</span>' if q["correct"] else f'<span class="wrong">错误/丢分</span>'
            q_rows += (f"<tr><td>{q['qid']}</td><td>{q['section']}</td><td>{q['qtype']}</td>"
                       f"<td>{q['full_score']:.0f}</td><td>{q['got_score']:.0f}</td><td>{status}</td>"
                       f"<td>{q['student_answer'] or '—'}</td><td>{q['correct_answer'] or '—'}</td>"
                       f"<td>{q['knowledge_point'] or '未标注'}</td></tr>")
        extra = f"""
    <h2>五、逐题作答情况</h2>
    <table>
      <tr><th>题号</th><th>板块</th><th>题型</th><th>满分</th><th>得分</th><th>正误</th><th>学生答案</th><th>正确答案</th><th>知识点</th></tr>
      {q_rows}
    </table>"""

    footer_date = meta.get("date", "")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>{CSS}</head>
<body><div class="page">
  <div class="header">
    <div class="title">{title}</div>
    <div class="sub">{sub}</div>
    {meta_line}
  </div>
  {cards}
  {part1}
  {part2}
  {part3}
  {part4}
  {extra}
  <div class="footer">由 试卷分析系统 生成{f' · {footer_date}' if footer_date else ''} · 仅供教学参考</div>
</div></body></html>"""
    return html


def save_html(analysis: dict, meta: dict, advice: dict, study_plan: list, mode: str = "individual") -> Path:
    html = build_html(analysis, meta, advice, study_plan, mode)
    out = TMP_DIR / f"report_{meta.get('report_id', 'tmp')}.html"
    out.write_text(html, encoding="utf-8")
    return out
