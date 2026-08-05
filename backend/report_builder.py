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
from .knowledge import SECTION_INDEX, knowledge_desc

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
  body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #eef2f7; color: #2b3445; }
  .page { max-width: 820px; margin: 0 auto; background: #ffffff; padding: 32px 38px 24px; box-shadow: 0 2px 20px rgba(31,58,122,.10); }
  .header { text-align: center; padding-bottom: 16px; border-bottom: 2px solid #dbe4f0; margin-bottom: 20px; }
  .header .title { font-size: 23px; font-weight: 800; color: #1f3a7a; letter-spacing: 4px; }
  .header .sub { margin-top: 8px; font-size: 13px; color: #7a8aa5; }
  .header .meta { margin-top: 12px; font-size: 13px; color: #5a6b85; }
  .header .meta span { margin: 0 16px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 11px; color: #fff; }
  .badge-easy { background: #2F9E6E; } .badge-mid { background: #D99A2B; }
  .badge-hard { background: #E8590C; } .badge-vhard { background: #D64545; }
  h2 { font-size: 15px; color: #1f3a7a; margin: 20px 0 10px; padding: 6px 12px; border-left: 4px solid #3B6FD4;
       background: linear-gradient(90deg,#eaf0fa,transparent); border-radius: 0 8px 8px 0; letter-spacing: 1px; }
  h3 { font-size: 14px; color: #4a5b75; margin: 16px 0 8px; }
  .cards { display: flex; gap: 12px; flex-wrap: wrap; }
  .card { flex: 1; min-width: 150px; background: linear-gradient(135deg,#2F5FA8,#4C7FD4); color: #fff;
          border-radius: 12px; padding: 14px 16px; box-shadow: 0 3px 10px rgba(47,95,168,.25); }
  .card .v { font-size: 22px; font-weight: 800; }
  .card .k { font-size: 12px; opacity: .92; margin-top: 3px; }
  .card.green { background: linear-gradient(135deg,#2F9E6E,#55B98A); box-shadow: 0 3px 10px rgba(47,158,110,.25); }
  .card.blue { background: linear-gradient(135deg,#3E7CB1,#6FA3D9); box-shadow: 0 3px 10px rgba(62,124,177,.25); }
  .card.gray { background: linear-gradient(135deg,#5b6b84,#8a99b3); box-shadow: 0 3px 10px rgba(91,107,132,.25); }
  table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 8px 0; border-radius: 8px; overflow: hidden; }
  th, td { border: 1px solid #e3e9f2; padding: 6px 8px; text-align: center; }
  th { background: #eaf0fa; color: #1f3a7a; font-weight: 700; font-size: 12px; }
  tr:nth-child(even) td { background: #f8fafd; }
  .right { color: #2F9E6E; font-weight: 700; } .wrong { color: #D64545; font-weight: 700; }
  .note { font-size: 12px; color: #5a6b85; line-height: 1.9; background: #f5f8fc; border-radius: 8px; padding: 12px 16px; }
  .video-tag { display: inline-block; background: #eaf0fa; color: #1f3a7a; border-radius: 6px; padding: 2px 8px;
               font-size: 11px; margin: 2px 4px 2px 0; }
  .video-tag a { color: inherit; text-decoration: none; }
  .video-tag a:hover { text-decoration: underline; }
  .more-vids { font-size: 11px; color: #7a8aa5; margin-top: 3px; line-height: 1.5; }
  .footer { margin-top: 26px; padding-top: 12px; border-top: 1px dashed #d5deeb; text-align: center;
            font-size: 12px; color: #6b7c96; letter-spacing: 1px; }
  .chart { text-align: center; margin: 8px 0; }
  .chart img { max-width: 100%; }
  .encourage { background: linear-gradient(135deg,#eef4fd,#f8fbff); border: 1px solid #d5e2f5; border-radius: 12px;
               padding: 16px 20px; font-size: 13px; line-height: 2; color: #33445e; }
  .section-head { display: inline-block; background: #3B6FD4; color: #fff; border-radius: 6px; padding: 2px 10px; font-size: 12px; }
  .appendix { font-size: 11px; }
  .appendix th, .appendix td { padding: 4px 6px; }
  @media print { body { background: #fff; } .page { box-shadow: none; } }
</style>
"""


def _b64(img_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(img_bytes).decode()


def _g(x) -> str:
    """分数精确显示：100.0→100，37.5→37.5（不四舍五入、不出现尾零）"""
    try:
        return f"{float(x):g}"
    except (TypeError, ValueError):
        return str(x)


def _chart_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


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
    exam = (meta.get("exam_name") or "").strip()
    if mode == "individual":
        title = "个人试卷分析报告"
    else:
        title = f"{exam} · 试卷分析报告" if exam else "试卷分析报告"
    sub = f"{school} · 物理学科" if school else "物理学科 · 学情分析报告"

    # 顶部信息：老师 + 学生（不显示排名/班型/分数）
    meta_line = (f"<div class='meta'><span>老师：{meta.get('teacher', '')}</span>"
                 f"<span>学生：{meta.get('student', '')}</span></div>")

    # 顶部卡片：总得分 + 选择题得分率 + 非选择题得分率 + 试卷整体难度
    cards = f"""
    <div class="cards">
      <div class="card"><div class="v">{_g(analysis['total_got'])} / {_g(analysis['total_full'])}</div><div class="k">总得分（满分 {_g(analysis['total_full'])}）</div></div>
      <div class="card green"><div class="v">{_g(analysis['choice_got'])} / {_g(analysis['choice_full'])}</div><div class="k">选择题得分率 {analysis['choice_rate']:.0%}</div></div>
      <div class="card blue"><div class="v">{_g(analysis['nonchoice_got'])} / {_g(analysis['nonchoice_full'])}</div><div class="k">非选择题得分率 {analysis['nonchoice_rate']:.0%}</div></div>
      <div class="card gray"><div class="v">{analysis['overall_difficulty']}</div><div class="k">试卷整体难度</div></div>
    </div>"""

    # 一、试卷整体分析：文字分析在前，板块表格在后
    sec_rows = ""
    for s in analysis["sections"]:
        sec_rows += (f"<tr><td><span class='section-head'>{s['name']}</span></td>"
                     f"<td>{s['gaokao_weight']:.0%}</td><td>{s['importance']}</td>"
                     f"<td>{_g(s['got_score'])} / {_g(s['full_score'])}</td>"
                     f"<td>{s['rate']:.0%}</td><td>{_g(s['lost_score'])}</td>"
                     f"<td>{difficulty_badge(s['difficulty'])}</td></tr>")
    part1 = f"""
    <h2>一、试卷整体分析</h2>
    <div class="note">{advice.get('paper_comment', '')}</div>
    <table>
      <tr><th>板块</th><th>高考占比</th><th>重要性</th><th>得分</th><th>得分率</th><th>丢分</th><th>难度</th></tr>
      {sec_rows}
    </table>
    <div class="note">{advice.get('section_importance', '')}</div>"""

    # 二、待巩固题目：每个错题一行（题目序号、板块、待提升、考察知识点+20字说明）
    wrong_rows = ""
    for q in analysis["per_question"]:
        if q["lost_score"] <= 0:
            continue
        kp = q["knowledge_point"] or "待补充"
        desc = knowledge_desc(kp)
        if desc and "详见" in desc:  # 防御：导入的大纲若含占位说明则不展示
            desc = ""
        kp_html = f"{kp}" + (f"<div class='kp-desc'>{desc}</div>" if desc else "")
        wrong_rows += (f"<tr><td>{q['qid']}</td><td>{q['section']}</td>"
                       f"<td class='wrong'>{_g(q['lost_score'])}</td>"
                       f"<td style='text-align:left'>{kp_html}</td></tr>")
    part2 = f"""
    <h2>二、待巩固题目</h2>
    <table>
      <tr><th>题目序号</th><th>板块</th><th>待提升分</th><th>考察知识点</th></tr>
      {wrong_rows or '<tr><td colspan="4">本次考试全部题目均已完成得很好，继续保持！</td></tr>'}
    </table>"""

    # 三、强化学习：以匹配的视频为核心，按视频归类强化知识点与针对题目（题号）
    # 每个知识点只取主推视频（第一个）建行，其余折叠为“＋N 个相关视频”，避免错题重复匹配
    video_rows = []
    video_index = {}
    for item in study_plan:
        qids = [str(q["qid"]) for q in item["questions"]]
        vids = item.get("videos") or []
        if vids:
            main = vids[0]
            key = main["title"]
            row = video_index.get(key)
            if row is None:
                row = {"title": key, "url": main.get("url", ""), "kps": [], "qids": [], "more": []}
                video_index[key] = row
                video_rows.append(row)
            if item["knowledge_point"] not in row["kps"]:
                row["kps"].append(item["knowledge_point"])
            for qid in qids:
                if qid not in row["qids"]:
                    row["qids"].append(qid)
            for v in vids[1:]:
                if v["title"] not in row["more"]:
                    row["more"].append(v["title"])
        else:
            # 目录为空时（仅个人模式可能出现）：集中到一行提示
            key = "__none__"
            row = video_index.get(key)
            if row is None:
                row = {"title": "", "url": "", "kps": [], "qids": [], "more": []}
                video_index[key] = row
                video_rows.append(row)
            if item["knowledge_point"] not in row["kps"]:
                row["kps"].append(item["knowledge_point"])
            for qid in qids:
                if qid not in row["qids"]:
                    row["qids"].append(qid)
    plan_rows = ""
    if video_rows:
        for row in video_rows:
            if row["title"]:
                vid_html = f'<span class="video-tag">{row["title"]}</span>'
                if row["url"]:
                    vid_html = (f'<span class="video-tag"><a href="{row["url"]}" '
                                f'target="_blank">{row["title"]}</a></span>')
                if row["more"]:
                    shown = row["more"][:2]
                    tail = "等" if len(row["more"]) > 2 else ""
                    vid_html += (f"<div class='more-vids'>＋{len(row['more'])} 个相关视频："
                                 f"{'、'.join(shown)}{tail}</div>")
            else:
                vid_html = '<span style="color:#99a5b8;font-size:12px">学科配置中暂无知识视频（导入后自动匹配）</span>'
            plan_rows += (f"<tr><td style='text-align:left'>{vid_html}</td>"
                          f"<td style='text-align:left'>{'、'.join(row['kps'])}</td>"
                          f"<td>{'、'.join(row['qids'])}</td></tr>")
    else:
        plan_rows = '<tr><td colspan="3">本次考试没有需要强化的丢分知识点，保持当前节奏即可。</td></tr>'
    part3 = f"""
    <h2>三、强化学习</h2>
    <table>
      <tr><th>匹配视频</th><th>强化知识点</th><th>针对题目（题号）</th></tr>
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
                   f"<td>{_g(q['full_score'])}</td><td>{_g(q['got_score'])}</td><td>{status}</td>"
                   f"<td>{q['student_answer'] or '—'}</td><td>{q['correct_answer'] or '—'}</td>"
                   f"<td>{q['knowledge_point'] or '待补充'}</td></tr>")
    extra = f"""
    <h2>附：答题明细</h2>
    <div class="table-wrap"><table class="appendix">
      <tr><th>题号</th><th>板块</th><th>题型</th><th>分值</th><th>得分</th><th>作答情况</th><th>学生答案</th><th>正确答案</th><th>知识点</th></tr>
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
  <div class="footer">每天进步一点点，成为更优秀的自己！{f' · {footer_date}' if footer_date else ''}</div>
</div></body></html>"""
    return html


def save_html(analysis: dict, meta: dict, advice: dict, study_plan: list, mode: str = "individual") -> Path:
    html = build_html(analysis, meta, advice, study_plan, mode)
    out = TMP_DIR / f"report_{meta.get('report_id', 'tmp')}.html"
    out.write_text(html, encoding="utf-8")
    return out
