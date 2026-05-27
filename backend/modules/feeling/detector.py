"""
感情侦测器实现
基于规则和关键词匹配的情绪分析
"""

import re
from typing import Dict, Optional, Any
import json

from modules.logger import log, exception


class FeelingDetector:
    """
    感情侦测器
    根据用户输入分析情绪状态
    """

    def __init__(self, llm_client=None):
        """
        初始化感情侦测器

        Args:
            llm_client: LLM 客户端，用于增强情绪分析（可选）
        """
        self.llm_client = llm_client

        # 情绪关键词配置
        self.emotion_keywords = {
            "angry": [
                "生气", "愤怒", "火大", "讨厌", "烦", "烦死人", "气死", "暴怒",
                "怒", "恼火", "不耐烦", "不满", "抱怨", "投诉", "垃圾", "差评",
                "什么鬼", "搞什么", "无语", "崩溃", "受不了", "不想听", "滚",
                "骗子", "骗钱", "退款", "维权", "投诉", "抗议", "太过分"
            ],
            "cheerful": [
                "开心", "高兴", "快乐", "幸福", "太棒", "太好了", "哇", "耶",
                "兴奋", "激动", "美滋滋", "爽", "赞", "优秀", "厉害", "牛",
                "漂亮", "完美", "惊喜", "感动", "感谢", "感恩", "爱你", "喜欢你",
                "天气真好", "心情好", "不错", "可以"
            ],
            "depressed": [
                "难过", "伤心", "失望", "沮丧", "失落", "郁闷", "无聊", "寂寞",
                "孤独", "绝望", "累", "疲惫", "压力大", "焦虑", "烦躁", "迷茫",
                "不想动", "没兴趣", "没意思", "想死", "活着好累", "撑不住",
                "太难了", "想哭", "心碎", "绝望", "无助", "迷茫"
            ],
            "friendly": [
                "谢谢", "麻烦你", "劳驾", "请", "您好", "你好", "辛苦了",
                "感谢", "帮忙", "请教", "请问", "麻烦", "打扰", "多谢",
                "客气", "不用谢", "没关系", "不好意思", "抱歉", "谅解"
            ],
            "upbeat": [
                "加油", "努力", "奋斗", "冲", "坚持", "相信", "一定",
                "可以的", "没问题", "有信心", "充满希望", "积极", "乐观",
                "干劲", "动力", "激情", "拼搏", "前进", "奋斗", "目标"
            ]
        }

        # 情绪评分权重
        self.emotion_score_weights = {
            "default": 5,
            "upbeat": 3,
            "angry": 7,
            "cheerful": 3,
            "depressed": 7,
            "friendly": 2
        }

        # 情绪分类指南描述
        self.emotion_guide = {
            "default": "中性或普通的情绪状态",
            "upbeat": "积极向上、充满干劲的状态",
            "angry": "愤怒、不满、生气的情绪",
            "cheerful": "欢快、喜悦的情绪",
            "depressed": "消极、低落、压抑的情绪",
            "friendly": "友好、亲切的情绪"
        }

    def _count_keywords(self, text: str, keywords: list) -> int:
        """
        统计文本中关键词出现的次数

        Args:
            text: 输入文本
            keywords: 关键词列表

        Returns:
            关键词出现次数
        """
        count = 0
        for keyword in keywords:
            count += len(re.findall(re.escape(keyword), text))
        return count

    def _analyze_by_rules(self, text: str) -> Dict[str, Any]:
        """
        使用规则进行情绪分析

        Args:
            text: 输入文本

        Returns:
            情绪分析结果 {"feeling": str, "score": int}
        """
        emotion_scores = {}

        # 统计每种情绪的关键词匹配数
        for emotion, keywords in self.emotion_keywords.items():
            count = self._count_keywords(text, keywords)
            if count > 0:
                emotion_scores[emotion] = count

        if not emotion_scores:
            return None

        # 找出匹配数最多的情绪
        max_emotion = max(emotion_scores, key=emotion_scores.get)
        max_count = emotion_scores[max_emotion]

        # 根据匹配程度计算分数（1-10）
        base_score = self.emotion_score_weights[max_emotion]
        score = min(10, base_score + max_count - 1)

        return {"feeling": max_emotion, "score": score}

    def _analyze_by_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """
        使用 LLM 进行情绪分析（增强模式）

        Args:
            text: 输入文本

        Returns:
            情绪分析结果 {"feeling": str, "score": int}，失败返回 None
        """
        if not self.llm_client:
            return None

        prompt = f"""请根据以下规则分析用户输入的情绪：
        情绪分类指南:
        1. default: 用于表达中性或普通的情绪状态
        2. upbeat: 用于表达积极向上、充满干劲的状态
        3. angry: 用于表达愤怒、不满、生气的情绪
        4. cheerful: 用于表达欢快、喜悦的情绪
        5. depressed: 用于表达消极、低落、压抑的情绪
        6. friendly: 用于表达友好、亲切的情绪

        示例:
        - "我特别生气！" -> {{"feeling": "angry", "score": 8}}
        - "今天天气真好" -> {{"feeling": "cheerful", "score": 2}}
        - "随便吧，都可以" -> {{"feeling": "default", "score": 5}}
        - "我很难过" -> {{"feeling": "depressed", "score": 9}}
        - "谢谢你的帮助" -> {{"feeling": "friendly", "score": 1}}

        用户输入内容: {text}

        请根据以上规则分析情绪并返回相应的feeling和score，只返回JSON格式。"""

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content
            
            json_match = re.search(r'\{[^{}]*"feeling"[^{}]*"score"[^{}]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                return result
            
            result = json.loads(content)
            return result
        except Exception as e:
            exception(f"LLM 情绪分析失败: {e}", "FeelingDetector", e)
            return None

    def detect(self, text: str) -> Dict[str, Any]:
        """
        检测用户输入的情绪

        Args:
            text: 用户输入文本
            use_llm: 是否使用 LLM 进行增强分析

        Returns:
            情绪分析结果 {"feeling": str, "score": int}
        """
        if not text or not isinstance(text, str):
            return {"feeling": "default", "score": 5}

        # rule_result = self._analyze_by_rules(text)
        # if rule_result: return rule_result

        llm_result = self._analyze_by_llm(text)
        if llm_result: return llm_result

        return {"feeling": "default", "score": 5}

    def get_emotion_info(self, feeling: str) -> Optional[str]:
        """
        获取情绪类型的描述信息

        Args:
            feeling: 情绪类型名称

        Returns:
            情绪描述信息
        """
        return self.emotion_guide.get(feeling)

    def get_all_emotions(self) -> list:
        """
        获取所有支持的情绪类型

        Returns:
            情绪类型列表
        """
        return list(self.emotion_guide.keys())
