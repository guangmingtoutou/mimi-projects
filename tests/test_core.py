# -*- coding: utf-8 -*-
"""核心逻辑单元测试：判分、设置安全、视频标题过滤。
运行：python -m unittest discover -s tests -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.analyzer import Question, analyze, grade_question
from backend.knowledge import is_video_title, knowledge_desc, load_outline


class TestGrading(unittest.TestCase):
    """判分引擎测试"""

    def test_single_choice(self):
        q = Question(qid="1", section_key="lixue", qtype="single", full_score=4,
                     student_answer="B", correct_answer="B")
        self.assertEqual(grade_question(q), 4)
        q = Question(qid="1", section_key="lixue", qtype="single", full_score=4,
                     student_answer="B", correct_answer="C")
        self.assertEqual(grade_question(q), 0)

    def test_multi_choice(self):
        q = Question(qid="2", section_key="lixue", qtype="multi", full_score=5,
                     student_answer="A,C", correct_answer="C,A", partial_score=2)
        self.assertEqual(grade_question(q, multi_partial=True), 5)   # 顺序无关
        q2 = Question(qid="2", section_key="lixue", qtype="multi", full_score=5,
                      student_answer="A", correct_answer="A,C", partial_score=2)
        self.assertEqual(grade_question(q2, multi_partial=True), 2)  # 选对不全
        self.assertEqual(grade_question(q2, multi_partial=False), 0)  # 未开启部分分
        q3 = Question(qid="2", section_key="lixue", qtype="multi", full_score=5,
                      student_answer="A,B", correct_answer="A,C")
        self.assertEqual(grade_question(q3), 0)                       # 有选错

    def test_calculation(self):
        # 答案带冒号 vs 标准答案纯字母
        q = Question(qid="13", section_key="lixue", qtype="calculation", full_score=12,
                     student_answer="C：f=4N a=1m/s²", correct_answer="C")
        self.assertEqual(grade_question(q), 12)
        # 双方纯字母
        q = Question(qid="14", section_key="lixue", qtype="calculation", full_score=12,
                     student_answer="C", correct_answer="C")
        self.assertEqual(grade_question(q), 12)
        # 字母不符
        q = Question(qid="15", section_key="lixue", qtype="calculation", full_score=12,
                     student_answer="B：...", correct_answer="C")
        self.assertEqual(grade_question(q), 0)
        # 无字母时规范化文本比较（4 N == 4N）
        q = Question(qid="16", section_key="lixue", qtype="calculation", full_score=6,
                     student_answer="4 N", correct_answer="4N")
        self.assertEqual(grade_question(q), 6)

    def test_analyze_stats(self):
        questions = [
            Question(qid="1", section_key="lixue", qtype="single", full_score=4,
                     got_score=2, knowledge_point="牛顿运动定律"),
            Question(qid="2", section_key="dianci", qtype="multi", full_score=5,
                     got_score=5, knowledge_point="静电场基本性质"),
            Question(qid="13", section_key="lixue", qtype="calculation", full_score=12,
                     got_score=6, knowledge_point="动量与动量守恒"),
        ]
        res = analyze(questions)
        self.assertEqual(res["total_full"], 21)
        self.assertEqual(res["total_got"], 13)
        # 选择题（单选+多选）得分率 7/9；非选择题 6/12
        self.assertAlmostEqual(res["choice_rate"], 7 / 9, places=3)
        self.assertAlmostEqual(res["nonchoice_rate"], 0.5, places=3)
        self.assertEqual(len(res["sections"]), 2)
        # 知识点丢分聚合（牛顿运动定律 2 分 + 动量 6 分）
        self.assertEqual(len(res["knowledge_loss"]), 2)

    def test_choice_rates_empty(self):
        """只有非选择题时选择题得分率为 0（不除零）"""
        res = analyze([Question(qid="13", section_key="lixue", qtype="calculation",
                                full_score=12, got_score=6, knowledge_point="动量与动量守恒")])
        self.assertEqual(res["choice_rate"], 0)
        self.assertAlmostEqual(res["nonchoice_rate"], 0.5)

    def test_score_reconciliation(self):
        """小数分值下 得分+丢分 必须严格等于 总分（100），板块级别同样成立"""
        qs = [
            Question(qid="1", section_key="lixue", qtype="single", full_score=12.5,
                     got_score=2.5, knowledge_point="牛顿运动定律"),
            Question(qid="2", section_key="lixue", qtype="single", full_score=12.5,
                     got_score=12.5, knowledge_point="牛顿运动定律"),
            Question(qid="3", section_key="dianci", qtype="multi", full_score=10.0,
                     got_score=5.0, knowledge_point="电磁感应"),
            Question(qid="4", section_key="dianci", qtype="calculation", full_score=65.0,
                     got_score=17.5, knowledge_point="电磁感应"),
        ]
        res = analyze(qs)
        self.assertEqual(res["total_full"], 100)
        self.assertEqual(res["total_got"], 37.5)
        self.assertEqual(res["total_lost"], 62.5)
        self.assertEqual(round(res["total_got"] + res["total_lost"], 1), res["total_full"])
        # 板块级：得分 + 丢分 = 板块满分
        for s in res["sections"]:
            self.assertEqual(round(s["got_score"] + s["lost_score"], 1), s["full_score"],
                             f"板块 {s['name']} 得分+丢分≠满分")
        self.assertEqual(round(sum(s["got_score"] for s in res["sections"]), 1), res["total_got"])
        # 逐题：丢分 = 分值 - 得分
        for q in res["per_question"]:
            self.assertEqual(round(q["got_score"] + q["lost_score"], 1), q["full_score"], f"题 {q['qid']}")


class TestSettingsSecurity(unittest.TestCase):
    """settings.json 的 Key 保护逻辑"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        from backend import config
        self._orig = config.SETTINGS_FILE
        config.SETTINGS_FILE = self.tmpdir / "settings.json"

    def tearDown(self):
        from backend import config
        config.SETTINGS_FILE = self._orig

    def test_key_protection(self):
        from backend import config
        config.save_settings({"llm_api_key": "sk-test-123"})
        self.assertEqual(config.load_settings()["llm_api_key"], "sk-test-123")
        # 空 Key 不应覆盖旧值
        config.save_settings({"llm_api_key": "", "school_name": "测试中学"})
        self.assertEqual(config.load_settings()["llm_api_key"], "sk-test-123")
        self.assertEqual(config.load_settings()["school_name"], "测试中学")
        # 显式清除
        config.clear_api_key()
        self.assertEqual(config.load_settings()["llm_api_key"], "")


class TestVideoTitle(unittest.TestCase):
    """OCR 视频标题过滤"""

    def test_filter(self):
        self.assertTrue(is_video_title("1.1.1.1匀变速直线运动的基础公式【目标专属】"))
        self.assertFalse(is_video_title("共120个视频"))
        self.assertFalse(is_video_title("3:45 播放"))
        self.assertFalse(is_video_title("短"))


class TestOutline(unittest.TestCase):
    """高考物理知识大纲"""

    def test_outline_loaded(self):
        o = load_outline()
        self.assertGreaterEqual(len(o["sections"]), 6)
        n = sum(len(s["knowledge_points"]) for s in o["sections"])
        self.assertGreaterEqual(n, 20)

    def test_knowledge_desc(self):
        self.assertTrue(knowledge_desc("匀变速直线运动"))
        self.assertEqual(knowledge_desc("不存在的知识点"), "")


class TestStudentCall(unittest.TestCase):
    """学生称呼规则"""

    def test_call(self):
        from backend.llm import student_call
        self.assertEqual(student_call("张伟"), "张伟同学")
        self.assertEqual(student_call("李小明"), "小明同学")
        self.assertEqual(student_call("欧阳娜娜"), "娜娜同学")
        self.assertEqual(student_call(""), "同学")


class TestReportStructure(unittest.TestCase):
    """报告 HTML 结构"""

    def test_build_html(self):
        from backend.report_builder import build_html
        qs = [
            Question(qid="1", section_key="lixue", qtype="single", full_score=4,
                     got_score=0, knowledge_point="牛顿运动定律"),
            Question(qid="2", section_key="dianci", qtype="multi", full_score=5,
                     got_score=5, knowledge_point="电磁感应"),
        ]
        analysis = analyze(qs)
        advice = {"paper_comment": "评析", "section_importance": "占比",
                  "study_advice": "建议", "encouragement": "加油"}
        html = build_html(analysis, {"teacher": "张老师", "student": "欧阳娜娜"}, advice, [])
        for marker in ["选择题得分率", "非选择题得分率", "试卷整体难度",
                       "一、试卷整体分析", "二、待巩固题目", "三、强化学习",
                       "四、总结", "附：答题明细"]:
            self.assertIn(marker, html)
        self.assertNotIn("📺", html)          # 无 emoji 乱码
        self.assertNotIn("排名", html.split("附：答题明细")[0])
        self.assertNotIn("班型：", html)
        # v0.5：圆环图已删除、章节改名、页脚鼓励语
        self.assertNotIn("各板块得分占比", html)
        self.assertNotIn("由 试卷分析系统 生成", html)
        self.assertIn("每天进步一点点，成为更优秀的自己！", html)

    def test_build_html_exam_name(self):
        """考试名称：填写后显示在标题，留空不显示"""
        from backend.report_builder import build_html
        qs = [Question(qid="1", section_key="lixue", qtype="single", full_score=4,
                       got_score=4, knowledge_point="牛顿运动定律")]
        analysis = analyze(qs)
        advice = {"paper_comment": "", "section_importance": "", "study_advice": "", "encouragement": ""}
        html = build_html(analysis, {"teacher": "张老师", "student": "张三", "exam_name": "高一期中考试"},
                          advice, [], mode="batch")
        self.assertIn("高一期中考试 · 试卷分析报告", html)
        html2 = build_html(analysis, {"teacher": "张老师", "student": "张三", "exam_name": "  "},
                           advice, [], mode="batch")
        self.assertIn("试卷分析报告", html2)
        self.assertNotIn("· 试卷分析报告", html2)

    def test_build_html_video_centric_plan(self):
        """强化学习表：每知识点一行，视频列在前（最多3个），错题不重复"""
        from backend.report_builder import build_html
        qs = [Question(qid="3", section_key="lixue", qtype="single", full_score=6,
                       got_score=0, knowledge_point="牛顿运动定律"),
              Question(qid="7", section_key="lixue", qtype="single", full_score=6,
                       got_score=2, knowledge_point="动量与动量守恒")]
        analysis = analyze(qs)
        advice = {"paper_comment": "", "section_importance": "", "study_advice": "", "encouragement": ""}
        plan = [
            {"knowledge_point": "牛顿运动定律", "questions": [{"qid": "3"}],
             "videos": [{"title": "1.2.1.1牛顿运动定律精讲", "url": ""}]},
            {"knowledge_point": "动量与动量守恒", "questions": [{"qid": "7"}],
             "videos": [{"title": "1.5.2.1动量守恒精讲", "url": ""}]},
        ]
        html = build_html(analysis, {"teacher": "张老师", "student": "张三"}, advice, plan, mode="batch")
        # 表头
        self.assertIn("匹配视频", html)
        self.assertIn("针对题目（题号）", html)
        self.assertNotIn("针对题型", html)
        # 每个知识点一行，各自视频与题号
        self.assertIn("1.2.1.1牛顿运动定律精讲", html)
        self.assertIn("1.5.2.1动量守恒精讲", html)
        self.assertIn("牛顿运动定律", html)
        self.assertIn("动量与动量守恒", html)
        self.assertIn(">3<", html)
        self.assertIn(">7<", html)
        self.assertNotIn("暂无匹配视频", html)

    def test_report_plan_three_videos_per_row(self):
        """每个知识点最多展示 3 个视频（不再折叠），错题只出现一次"""
        from backend.report_builder import build_html
        qs = [Question(qid="3", section_key="lixue", qtype="single", full_score=6,
                       got_score=0, knowledge_point="牛顿运动定律")]
        analysis = analyze(qs)
        advice = {"paper_comment": "", "section_importance": "", "study_advice": "", "encouragement": ""}
        plan = [
            {"knowledge_point": "牛顿运动定律", "questions": [{"qid": "3"}],
             "videos": [{"title": "1.2.1.1牛顿运动定律精讲", "url": ""},
                         {"title": "1.3.2.1超重与失重问题", "url": ""},
                         {"title": "1.3.2.2斜面动力学问题", "url": ""}]},
        ]
        html = build_html(analysis, {"teacher": "张老师", "student": "张三"}, advice, plan, mode="batch")
        for t in ["1.2.1.1牛顿运动定律精讲", "1.3.2.1超重与失重问题", "1.3.2.2斜面动力学问题"]:
            self.assertEqual(html.count(t), 1)  # 每个视频只出现一次
        self.assertNotIn("＋2 个相关视频", html)
        self.assertNotIn("more-vids", html)

    def test_match_videos_section_boundary(self):
        """板块强约束：力学知识点绝不匹配到电磁学视频（含关键词误命中场景）"""
        from unittest import mock
        from backend.knowledge import match_videos
        videos = [
            {"title": "1.1.1.1匀变速直线运动的基础公式", "url": "", "kp": ["匀变速直线运动"]},
            {"title": "2.1.1.1库仑定律", "url": "", "kp": ["静电场基本性质"]},
            {"title": "2.1.5.2带电粒子在电场中的曲线运动", "url": "", "kp": ["静电场基本性质"]},
        ]
        with mock.patch("backend.knowledge.load_catalog", return_value=videos):
            # “曲线运动与平抛”关键词会命中“带电粒子在电场中的曲线运动”，但板块约束下只返回力学视频
            got = match_videos("曲线运动与平抛", "目标班")
            self.assertTrue(got)
            for v in got:
                self.assertNotIn("带电粒子在电场中的曲线运动", v["title"])
                self.assertNotIn("库仑定律", v["title"])
            # 电磁知识点返回电磁视频
            got2 = match_videos("静电场基本性质", "目标班")
            self.assertTrue(any("库仑定律" in v["title"] for v in got2))
            self.assertTrue(all("匀变速直线运动" not in v["title"] for v in got2))

    def test_report_exact_scores(self):
        """报告分数精确显示（不四舍五入成整数），得分+丢分=100"""
        from backend.report_builder import build_html
        qs = [
            Question(qid="1", section_key="lixue", qtype="single", full_score=12.5,
                     got_score=2.5, knowledge_point="牛顿运动定律"),
            Question(qid="2", section_key="lixue", qtype="single", full_score=12.5,
                     got_score=12.5, knowledge_point="牛顿运动定律"),
            Question(qid="3", section_key="dianci", qtype="multi", full_score=10.0,
                     got_score=5.0, knowledge_point="电磁感应"),
            Question(qid="4", section_key="dianci", qtype="calculation", full_score=65.0,
                     got_score=17.5, knowledge_point="电磁感应"),
        ]
        analysis = analyze(qs)
        advice = {"paper_comment": "", "section_importance": "", "study_advice": "", "encouragement": ""}
        html = build_html(analysis, {"teacher": "张老师", "student": "张三"}, advice, [])
        # 卡片精确显示 37.5 / 100，而不是四舍五入的 38 / 100
        self.assertIn("37.5 / 100", html)
        self.assertNotIn("38 / 100", html)
        # 板块行：丢分精确（力学 15/25 丢 10，电磁 22.5/75 丢 52.5）
        self.assertIn("15 / 25", html)
        self.assertIn("52.5", html)

    def test_outline_no_placeholder(self):
        """大纲所有知识点说明不能是占位符"""
        from backend.knowledge import knowledge_desc, load_outline
        o = load_outline()
        for sec in o["sections"]:
            for kp in sec["knowledge_points"]:
                self.assertNotIn("详见", kp.get("desc", ""), f"知识点「{kp['name']}」说明仍是占位符")
                self.assertTrue((kp.get("desc") or "").strip(), f"知识点「{kp['name']}」说明为空")
        self.assertIn("向心力", knowledge_desc("圆周运动"))

    def test_match_videos_force(self):
        """知识视频强制匹配：目录非空时任意知识点都能匹配到视频"""
        from backend.knowledge import load_catalog, match_videos
        if not load_catalog("目标班"):
            self.skipTest("目标班视频目录为空")
        vids = match_videos("完全不存在的知识点XYZ", "目标班")
        self.assertTrue(vids)

    def test_section_key_for_kp(self):
        """知识点自动反查板块（前端漏传 section_key 时兜底）"""
        from backend.knowledge import section_key_for_kp
        self.assertEqual(section_key_for_kp("牛顿运动定律"), "lixue")
        self.assertEqual(section_key_for_kp("电磁感应"), "dianci")
        self.assertEqual(section_key_for_kp("不存在的知识点"), "lixue")
        self.assertEqual(section_key_for_kp(""), "lixue")

    def test_suggest_kp_for_video(self):
        """视频标题自动匹配大纲知识点（可多选，供学科配置预填）"""
        from backend.knowledge import suggest_kp_for_video
        kps = suggest_kp_for_video("1.3.2.1超重与失重问题【目标专属】")
        self.assertIn("超重与失重", kps)
        kps2 = suggest_kp_for_video("2.4.1.1楞次定律综合问题")
        self.assertTrue(kps2)  # 至少匹配到一条（楞次定律相关）
        self.assertEqual(suggest_kp_for_video(""), [])
        self.assertEqual(suggest_kp_for_video("随便乱写的一行"), [])

    def test_match_videos_binding_first(self):
        """绑定优先：视频绑定了该知识点时，优先返回绑定视频而非关键词命中"""
        from unittest import mock
        from backend.knowledge import match_videos
        videos = [
            {"title": "1.1.1.1匀变速直线运动的基础公式", "url": "", "kp": ["牛顿运动定律"]},
            {"title": "2.4.1.1楞次定律综合问题", "url": "", "kp": ["电磁感应"]},
            {"title": "1.2.1.1牛顿运动定律精讲", "url": "", "kp": []},  # 标题含关键词但未绑定
        ]
        with mock.patch("backend.knowledge.load_catalog", return_value=videos):
            got = match_videos("牛顿运动定律", "目标班")
            self.assertEqual(got[0]["title"], "1.1.1.1匀变速直线运动的基础公式")  # 绑定视频优先
            got2 = match_videos("电磁感应", "目标班")
            self.assertEqual(got2[0]["title"], "2.4.1.1楞次定律综合问题")

    def test_common_substr_threshold(self):
        """公共子串阈值：3 字巧合子串（如“量守恒”）不算相近，4 字才算"""
        from backend.knowledge import _common_substr
        self.assertEqual(_common_substr("功能关系与能量守恒", "动量守恒定律"), "")   # 只有“量守恒”3字
        self.assertEqual(_common_substr("万有引力定律", "万有引力与天体运动"), "万有引力")
        self.assertEqual(_common_substr("圆周运动", "匀变速直线运动"), "")

    def test_match_videos_no_shared_fallback(self):
        """不同知识点不再共用同一批兑底视频（截图问题回归）"""
        from backend.knowledge import load_catalog, match_videos
        if not load_catalog("菁英班"):
            self.skipTest("菁英班目录为空")
        # 截图中的 4 个知识点：都不应再匹配到匀变速系列兑底视频
        fallback_vids = {"1.1.1.2初速度为零的匀加速直线运动",
                         "1.1.1.3匀变速直线运动的进阶公式【菁英专属】",
                         "1.1.2.1运动图像问题"}
        for kp in ["圆周运动与向心力", "万有引力定律", "功与功率", "功能关系与能量守恒"]:
            got = {v["title"] for v in match_videos(kp, "菁英班", limit=3)}
            self.assertFalse(got & fallback_vids, f"{kp} 仍命中兑底视频 {got & fallback_vids}")
        # 圆周运动与向心力 → 圆周运动系列（绑定包含关系）
        vids = match_videos("圆周运动与向心力", "菁英班", limit=3)
        self.assertTrue(any("圆周运动" in v["title"] for v in vids))
        # 万有引力定律 → 卫星/天体系列（相近知识点）
        vids = match_videos("万有引力定律", "菁英班", limit=3)
        self.assertTrue(any("卫星" in v["title"] or "天体" in v["title"] or "重力" in v["title"] for v in vids))
        # 功与功率 → 功率系列（自动拆词）
        vids = match_videos("功与功率", "菁英班", limit=3)
        self.assertTrue(any("功率" in v["title"] for v in vids))
        # 功能关系与能量守恒 → 能量系列（相近知识点）
        vids = match_videos("功能关系与能量守恒", "菁英班", limit=3)
        self.assertTrue(all("1.7." in v["title"] for v in vids))

    def test_batch_prereq_checks(self):
        """批量生成前检查：老师无学生 / 缺 API / 总分非100 / 视频目录为空"""
        from unittest import mock
        from backend.main import _check_batch_prereqs
        parsed = {"students": [
            {"name": "张三", "teacher": "张老师", "class_type": "目标班", "answers": {}},
            {"name": "李四", "teacher": "张老师", "class_type": "菁英班", "answers": {}},
        ]}
        qs100 = [{"qid": "1", "full_score": 100}]
        # 全部通过
        with mock.patch("backend.main.load_catalog", return_value=[{"title": "x"}]), \
             mock.patch("backend.main.llm_available", return_value=True):
            self.assertEqual(_check_batch_prereqs(parsed, "张老师", "目标班", "rule", qs100), [])
        # 老师名下无学生
        errs = _check_batch_prereqs(parsed, "王老师", "目标班", "rule", qs100)
        self.assertTrue(any("名下没有学生" in e for e in errs))
        # 非纯规则缺 API Key
        with mock.patch("backend.main.llm_available", return_value=False):
            errs = _check_batch_prereqs(parsed, "张老师", "目标班", "llm", qs100)
            self.assertTrue(any("API Key" in e for e in errs))
        # 总分不等于 100
        errs = _check_batch_prereqs(parsed, "张老师", "目标班", "rule", [{"qid": "1", "full_score": 90}])
        self.assertTrue(any("不是 100 分" in e for e in errs))
        # 视频目录为空
        with mock.patch("backend.main.load_catalog", return_value=[]):
            errs = _check_batch_prereqs(parsed, "张老师", "目标班", "rule", qs100)
            self.assertTrue(any("知识视频目录为空" in e for e in errs))
            self.assertIn("目标班", errs[0])
            self.assertIn("菁英班", errs[0])


if __name__ == "__main__":
    unittest.main()
