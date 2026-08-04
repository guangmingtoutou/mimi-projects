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
from backend.knowledge import is_video_title


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
        ]
        res = analyze(questions)
        self.assertEqual(res["total_full"], 9)
        self.assertEqual(res["total_got"], 7)
        self.assertEqual(res["overall_difficulty"], "中等")
        self.assertEqual(len(res["sections"]), 2)
        # 知识点丢分聚合
        self.assertEqual(len(res["knowledge_loss"]), 1)


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


if __name__ == "__main__":
    unittest.main()
