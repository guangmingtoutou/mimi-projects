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
        """强化学习表以匹配视频为核心：同一视频归集多个知识点与题号"""
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
             "videos": [{"title": "1.2.1.1牛顿运动定律精讲", "url": ""},
                         {"title": "1.5.2.1动量守恒精讲", "url": ""}]},
        ]
        html = build_html(analysis, {"teacher": "张老师", "student": "张三"}, advice, plan, mode="batch")
        # 表头
        self.assertIn("匹配视频", html)
        self.assertIn("针对题目（题号）", html)
        self.assertNotIn("针对题型", html)
        # 视频行：第一个视频归集两个知识点 + 题号 3、7；第二个视频只有动量 + 7
        self.assertIn("1.2.1.1牛顿运动定律精讲", html)
        self.assertIn("1.5.2.1动量守恒精讲", html)
        # 同一视频行内知识点与题号合并展示
        self.assertIn("牛顿运动定律、动量与动量守恒", html)
        self.assertIn("3、7", html)
        self.assertNotIn("暂无匹配视频", html)

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
