# -*- coding: utf-8 -*-
"""高考物理知识体系：板块、知识点、高考占比、重要程度、知识视频映射、知识大纲"""
import json
import re
from pathlib import Path

from .config import CATALOG_DIR, DATA_DIR

# 知识大纲文件（考察知识点引用；可导入更新）
OUTLINE_FILE = DATA_DIR / "outline.json"


def load_outline() -> dict:
    """加载高考物理知识大纲。返回 {"version":..., "sections":[{key,name,knowledge_points:[{name,desc}]}]}
    文件缺失时回退到内置 SECTIONS（desc 为空）。
    """
    if OUTLINE_FILE.exists():
        try:
            data = json.loads(OUTLINE_FILE.read_text(encoding="utf-8"))
            if data.get("sections"):
                return data
        except Exception:
            pass
    # 回退：从内置 SECTIONS 生成（desc 为空字符串）
    sections = [{"key": s["key"], "name": s["name"],
                 "knowledge_points": [{"name": k["name"], "desc": ""} for k in s["knowledge_points"]]}
                for s in SECTIONS]
    return {"version": "builtin", "sections": sections}


def save_outline(outline: dict) -> dict:
    """保存/更新知识大纲（导入接口用）"""
    import datetime
    outline["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    OUTLINE_FILE.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    return outline


def reset_outline() -> dict:
    """删除自定义大纲文件，回退到内置大纲"""
    OUTLINE_FILE.unlink(missing_ok=True)
    return load_outline()


def knowledge_desc(name: str) -> str:
    """按知识点名查大纲说明（找不到返回空串）"""
    for sec in load_outline().get("sections", []):
        for kp in sec.get("knowledge_points", []):
            if kp["name"] == name:
                return kp.get("desc", "")
    return ""

# ---------------------------------------------------------------
# 高考物理板块体系（新高考：必修 + 选择性必修，全部必考）
# 占比为参考值，可按实际试卷在设置中调整
# ---------------------------------------------------------------
SECTIONS = [
    {
        "key": "lixue",
        "name": "力学",
        "gaokao_weight": 0.35,
        "importance": "高",
        "description": "运动学、相互作用与牛顿定律、曲线运动、万有引力与天体、机械能、动量",
        "knowledge_points": [
            {"name": "匀变速直线运动", "keywords": ["匀变速", "自由落体", "竖直上抛", "刹车", "x-t", "v-t", "运动图像", "初速度为零", "匀加速直线"]},
            {"name": "相互作用与受力分析", "keywords": ["受力分析", "摩擦力", "弹力", "共点力平衡", "力的合成", "力的分解", "重力", "多物体平衡"]},
            {"name": "牛顿运动定律", "keywords": ["牛顿", "加速度", "整体法", "隔离法", "连接体", "传送带", "圆弧", "超重", "失重", "斜面", "弹簧", "板块", "倾斜弹力", "动力学"]},
            {"name": "曲线运动与平抛", "keywords": ["平抛", "曲线运动", "斜抛", "合运动", "分运动", "运动的合成", "球拍", "弹离", "足球", "抛出"]},
            {"name": "圆周运动", "keywords": ["圆周", "向心力", "临界", "圆锥摆", "水平转盘", "传动", "水平圆周", "秋千", "座椅", "缆绳", "圆盘", "摆锤", "打夯机", "陶罐", "转台", "角速度"]},
            {"name": "万有引力与天体运动", "keywords": ["万有引力", "卫星", "天体", "宇宙速度", "开普勒", "同步卫星", "地表重力", "环绕", "密度", "多星", "质量", "月球", "轨道", "变轨", "探测器", "火星"]},
            {"name": "机械能与功能关系", "keywords": ["动能定理", "机械能守恒", "功率", "功能关系", "重力势能", "机车启动", "连接体", "牵引力", "启动", "阻力", "路程", "动能", "做功"]},
            {"name": "动量与动量守恒", "keywords": ["动量", "碰撞", "反冲", "爆炸", "弹簧模型", "子弹打木块", "动量定理", "平均作用力", "非弹性", "木板", "滑上", "滑块"]},
            {"name": "机械振动与机械波", "keywords": ["简谐运动", "机械波", "波长", "周期", "波动图像", "多普勒", "波的叠加", "干涉"]},
        ],
    },
    {
        "key": "dianci",
        "name": "电磁学",
        "gaokao_weight": 0.35,
        "importance": "高",
        "description": "电场、恒定电流、磁场、电磁感应、交变电流",
        "knowledge_points": [
            {"name": "静电场基本性质", "keywords": ["电场强度", "电势", "电势差", "电场线", "等势面", "带电粒子在电场", "库仑", "电势能", "静电场"]},
            {"name": "电容器与带电粒子", "keywords": ["电容器", "平行板", "偏转", "加速电场", "示波器"]},
            {"name": "恒定电流与电路", "keywords": ["欧姆定律", "闭合电路", "电功率", "电表", "伏安特性", "串并联", "电源", "电流", "电阻", "动态分析"]},
            {"name": "磁场与安培力", "keywords": ["磁感应强度", "安培力", "电流在磁场", "磁感线", "通电导线"]},
            {"name": "带电粒子在磁场中运动", "keywords": ["洛伦兹力", "回旋", "轨迹", "磁场偏转", "质谱仪", "回旋加速器"]},
            {"name": "电磁感应", "keywords": ["法拉第", "楞次定律", "感应电动势", "动生", "感生", "自感", "双棒", "导轨", "棒阻", "框阻", "单棒"]},
            {"name": "交变电流与变压器", "keywords": ["交变电流", "有效值", "正弦", "变压器", "远距离输电", "瞬时值"]},
        ],
    },
    {
        "key": "rexue",
        "name": "热学",
        "gaokao_weight": 0.08,
        "importance": "中",
        "description": "分子动理论、气体实验定律、热力学定律",
        "knowledge_points": [
            {"name": "分子动理论与内能", "keywords": ["分子动理论", "内能", "布朗运动", "分子力", "热力学温标"]},
            {"name": "气体实验定律", "keywords": ["理想气体", "玻意耳", "查理", "盖吕萨克", "p-V", "气缸", "液柱", "状态方程"]},
            {"name": "热力学定律", "keywords": ["热力学第一定律", "热力学第二定律", "做功", "热传递", "能量守恒"]},
        ],
    },
    {
        "key": "guangxue",
        "name": "光学",
        "gaokao_weight": 0.08,
        "importance": "中",
        "description": "光的折射、全反射、干涉、衍射、光电效应",
        "knowledge_points": [
            {"name": "折射与全反射", "keywords": ["折射率", "全反射", "临界角", "光路", "棱镜"]},
            {"name": "光的干涉衍射偏振", "keywords": ["干涉", "衍射", "偏振", "双缝", "薄膜干涉"]},
            {"name": "光电效应与波粒二象性", "keywords": ["光电效应", "光子", "逸出功", "波粒二象性", "康普顿"]},
        ],
    },
    {
        "key": "yuanzi",
        "name": "原子物理",
        "gaokao_weight": 0.06,
        "importance": "中",
        "description": "原子结构、能级跃迁、核反应、质能方程",
        "knowledge_points": [
            {"name": "原子结构与能级", "keywords": ["玻尔", "能级", "跃迁", "氢原子", "光谱", "原子结构"]},
            {"name": "核反应与核能", "keywords": ["核反应", "衰变", "半衰期", "质能方程", "结合能", "裂变", "聚变", "原子核"]},
        ],
    },
    {
        "key": "shiyan",
        "name": "实验",
        "gaokao_weight": 0.08,
        "importance": "高",
        "description": "力学实验、电学实验，渗透在各板块，单独计分",
        "knowledge_points": [
            {"name": "力学实验", "keywords": ["打点计时器", "探究加速度", "验证机械能守恒", "验证动量守恒", "测重力加速度", "纸带"]},
            {"name": "电学实验", "keywords": ["伏安法", "测电阻", "电表改装", "描绘伏安特性", "测电源电动势", "螺旋测微器", "游标卡尺"]},
        ],
    },
]

SECTION_INDEX = {s["key"]: s for s in SECTIONS}

# 题型及默认建议分值（可被试卷分值配置覆盖）
QUESTION_TYPES = [
    {"key": "single", "name": "单选题", "default_score": 4},
    {"key": "multi", "name": "多选题", "default_score": 5},
    {"key": "experiment", "name": "实验题", "default_score": 10},
    {"key": "calculation", "name": "计算题", "default_score": 15},
    {"key": "fill", "name": "填空题", "default_score": 6},
    {"key": "other", "name": "其他", "default_score": 5},
]

TYPE_INDEX = {t["key"]: t for t in QUESTION_TYPES}


# ---------------------------------------------------------------
# 知识视频目录：来自 OCR 识别的目录图片 / 手动导入
# 结构: {"class_type": "目标班|菁英班", "videos": [{"title": "...", "url": ""}, ...]}
# ---------------------------------------------------------------
def catalog_path(class_type: str) -> Path:
    return CATALOG_DIR / f"catalog_{class_type}.json"


def load_catalog(class_type: str) -> list:
    p = catalog_path(class_type)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("videos", [])
        except Exception:
            return []
    return []


def save_catalog(class_type: str, videos: list):
    catalog_path(class_type).write_text(
        json.dumps({"class_type": class_type, "videos": videos}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


_VIDEO_NOISE_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}")  # 形如 1.1.1.1


def is_video_title(title: str) -> bool:
    """判断 OCR 出来的行是否为真正的视频条目（形如 1.1.1.1xxx）"""
    t = title.strip()
    if len(t) < 6:
        return False
    return bool(_VIDEO_NOISE_RE.match(t))


def video_topic(title: str) -> str:
    """去掉编号前缀与【班型专属】后缀，得到主题名"""
    t = title.strip()
    m = re.match(r"^\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\s*(.*)$", t)
    if m:
        t = m.group(1)
    t = re.sub(r"【[^】]*】", "", t)
    return t.strip()


def match_videos(knowledge_point_name: str, class_type: str, limit: int = 3) -> list:
    """根据知识点关键词匹配知识视频（标题/主题包含知识点名或关键词）"""
    videos = load_catalog(class_type)
    if not videos:
        return []
    kp = None
    for sec in SECTIONS:
        for k in sec["knowledge_points"]:
            if k["name"] == knowledge_point_name:
                kp = k
                break
    keywords = []
    if kp:
        keywords = [kp["name"]] + kp["keywords"]
    scored = []
    for v in videos:
        title = v.get("title", "")
        topic = video_topic(title)
        score = 0
        for kw in keywords:
            if not kw:
                continue
            if kw in topic:
                score += 4
            elif kw in title:
                score += 3
        if knowledge_point_name and knowledge_point_name in topic:
            score += 6
        if score > 0:
            scored.append((score, v))
    scored.sort(key=lambda x: -x[0])
    return [v for _, v in scored[:limit]]
