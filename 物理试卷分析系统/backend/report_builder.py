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

PALETTE = ["#F08C4A", "#5FB7A2", "#F2B950", "#7FA8D9", "#C47BD1", "#E87A90", "#8FC1A9", "#D9A05B"]
PALETTE_HEX = ["F08C4A", "5FB7A2", "F2B950", "7FA8D9", "C47BD1", "E87A90", "8FC1A9", "D9A05B"]

CSS = """
<style>
  @page { size: A4; margin: 0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #faf3ea; color: #3d342c; }
  .page { max-width: 820px; margin: 0 auto; background: #fffdf9; padding: 32px 38px 24px; box-shadow: 0 2px 24px rgba(190,145,100,.14); }
  .header { text-align: center; padding-bottom: 16px; border-bottom: 2px solid #f5d0a8; margin-bottom: 20px; }
  .header .title { font-size: 23px; font-weight: 800; color: #e07b39; letter-spacing: 4px; }
  .header .sub { margin-top: 8px; font-size: 13px; color: #a8937f; }
  .header .meta { margin-top: 12px; font-size: 13px; color: #6b5d50; }
  .header .meta span { margin: 0 16px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 11px; color: #fff; }
  .badge-easy { background: #5FB7A2; } .badge-mid { background: #F2B950; }
  .badge-hard { background: #F08C4A; } .badge-vhard { background: #E07A7A; }
  h2 { font-size: 15px; color: #b55a24; margin: 20px 0 10px; padding: 6px 12px; border-left: 4px solid #f0a868;
       background: linear-gradient(90deg,#fdf1e4,transparent); border-radius: 0 8px 8px 0; letter-spacing: 1px; }
  h3 { font-size: 14px; color: #8a6b4f; margin: 16px 0 8px; }
  .cards { display: flex; gap: 12px; flex-wrap: wrap; }
  .card { flex: 1; min-width: 150px; background: linear-gradient(135deg,#F08C4A,#F7B26A); color: #fff;
          border-radius: 12px; padding: 14px 16px; box-shadow: 0 3px 10px rgba(240,140,74,.25); }
  .card .v { font-size: 22px; font-weight: 800; }
  .card .k { font-size: 12px; opacity: .92; margin-top: 3px; }
  .card.green { background: linear-gradient(135deg,#5FB7A2,#8AD1BC); box-shadow: 0 3px 10px rgba(95,183,162,.25); }
  .card.blue { background: linear-gradient(135deg,#7FA8D9,#A9C7E8); box-shadow: 0 3px 10px rgba(127,168,217,.25); }
  .card.gray { background: linear-gradient(135deg,#b9a898,#d3c4b2); box-shadow: 0 3px 10px rgba(185,168,152,.25); }
  table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 8px 0; border-radius: 8px; overflow: hidden; }
  th, td { border: 1px solid #f3e4d4; padding: 6px 8px; text-align: center; }
  th { background: #fbead7; color: #a05622; font-weight: 700; font-size: 12px; }
  tr:nth-child(even) td { background: #fdf8f1; }
  .right { color: #4DA58F; font-weight: 700; } .wrong { color: #D96B6B; font-weight: 700; }
  .note { font-size: 12px; color: #6b5d50; line-height: 1.9; background: #fdf6ec; border-radius: 8px; padding: 12px 16px; }
  .video-tag { display: inline-block; background: #fbead7; color: #b55a24; border-radius: 6px; padding: 2px 8px;
               font-size: 11px; margin: 2px 4px 2px 0; }
  .footer { margin-top: 26px; padding-top: 12px; border-top: 1px dashed #e8d5c0; text-align: center;
            font-size: 11px; color: #b5a28e; }
  .chart { text-align: center; margin: 8px 0; }
  .chart img { max-width: 100%; }
  .encourage { background: linear-gradient(135deg,#fff7ea,#fffdf6); border: 1px solid #f5d8ae; border-radius: 12px;
               padding: 16px 20px; font-size: 13px; line-height: 2; color: #7a5a38; }
  .section-head { display: inline-block; background: #F08C4A; color: #fff; border-radius: 6px; padding: 2px 10px; font-size: 12px; }
  .appendix { font-size: 11px; }
  .appendix th, .appendix td { padding: 4px 6px; }
  @media print { body { background: #fff; } .page { box-shadow: none; } }
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


def student_call(name: str) -> str:
    """学生称呼：两个字直接“XX同学”；超过两个字取后两个字加“同学”"""
    n = (name or "").strip()
    if not n:
        return "同学"
    if len(n) <= 2:
        return f"{n}同学"
    return f"{n[-2:]}同学"


def build_html(analysis: dict, meta: dict, advice: dict, study_plan: list, mode: str = "individual") -> str:
    """生成完整报告 HTML。meta: 老师/学生/学校等（不展示班型与排名）"""
    school = meta.get("school", "")
    title = "个人试卷分析报告" if mode == "individual" else "试卷分析报告"
    sub = f"{school} · 物理学科" if school else "物理学科 · 学情分析报告"

    # 顶部信息：老师 + 学生（不显示排名/班型/分数）
    meta_line = (f"<div class='meta'><span>老师：{meta.get('teacher', '')}</span>"
                 f"<span>学生：{meta.get('student', '')}</span></div>")

    # 顶部卡片：选择题得分率 / 非选择题得分率 / 试卷整体难度
    cards = f"""
    <div class="cards">
      <div class="card green"><div class="v">{analysis['choice_rate']:.0%}</div><div class="k">选择题得分率</div></div>
      <div class="card orange"><div class="v">{analysis['nonchoice_rate']:.0%}</div><div class="k">非选择题得分率</div></div>
      <div class="card gray"><div class="v">{analysis['overall_difficulty']}</div><div class="k">试卷整体难度</div></div>
    </div>"""

    # 一、试卷整体分析：文字分析在前，板块表格在后
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

    # 二、待巩固题目分析：每个错题一行（题目序号、板块、待提升、考察知识点）
    wrong_rows = ""
    for q in analysis["per_question"]:
        if q["lost_score"] <= 0:
            continue
        wrong_rows += (f"<tr><td>{q['qid']}</td><td>{q['section']}</td>"
                       f"<td class='wrong'>{q['lost_score']:.0f}</td>"
                       f"<td>{q['knowledge_point'] or '待补充'}</td></tr>")
    part2 = f"""
    <h2>二、待巩固题目分析</h2>
    <table>
      <tr><th>题目序号</th><th>板块</th><th>待提升分</th><th>考察知识点</th></tr>
      {wrong_rows or '<tr><td colspan="4">本次考试全部题目均已完成得很好，继续保持！</td></tr>'}
    </table>"""

    # 三、强化学习计划：表格（强化知识点、针对题型、对应强化学习视频；不显示丢分）
    qtype_map = {q["qid"]: q["qtype"] for q in analysis["per_question"]}
    plan_rows = ""
    if study_plan:
        for item in study_plan:
            types = "、".join(dict.fromkeys(
                qtype_map.get(q["qid"], "") for q in item["questions"] if qtype_map.get(q["qid"])))
            vids = "".join(f'<span class="video-tag">{v["title"]}</span>' for v in item["videos"])
            vids = vids or '<span style="color:#99a;font-size:12px">暂无匹配视频（可导入知识视频目录）</span>'
            plan_rows += (f"<tr><td>{item['knowledge_point']}</td><td>{types or '—'}</td><td>{vids}</td></tr>")
    else:
        plan_rows = '<tr><td colspan="3">本次考试没有需要强化的丢分知识点，保持当前节奏即可。</td></tr>'
    part3 = f"""
    <h2>三、强化学习计划</h2>
    <table>
      <tr><th>强化知识点</th><th>针对题型</th><th>对应强化学习视频</th></tr>
      {plan_rows}
    </table>"""

    # 四、总结（鼓励带学生称呼，建议围绕直播课/知识视频）
    part4 = f"""
    <h2>四、总结</h2>
    <div class="encourage">{advice.get('encouragement', '')}</div>
    <div class="note" style="margin-top:12px">{advice.get('study_advice', '')}</div>"""

    # 附：答题明细（原“五、逐题作答情况”）
    q_rows = ""
    for q in analysis["per_question"]:
        status = f'<span class="right">完成较好</span>' if q["correct"] else f'<span class="wrong">待巩固</span>'
        q_rows += (f"<tr><td>{q['qid']}</td><td>{q['section']}</td><td>{q['qtype']}</td>"
                   f"<td>{q['full_score']:.0f}</td><td>{q['got_score']:.0f}</td><td>{status}</td>"
                   f"<td>{q['student_answer'] or '—'}</td><td>{q['correct_answer'] or '—'}</td>"
                   f"<td>{q['knowledge_point'] or '待补充'}</td></tr>")
    extra = f"""
    <h2>附：答题明细</h2>
    <div class="table-wrap"><table class="appendix">
      <tr><th>题号</th><th>板块</th><th>题型</th><th>满分</th><th>得分</th><th>作答情况</th><th>学生答案</th><th>正确答案</th><th>知识点</th></tr>
      {q_rows}
    </table></div>"""

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
