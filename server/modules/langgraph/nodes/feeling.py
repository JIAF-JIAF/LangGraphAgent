"""
情绪检测节点

负责分析用户输入的情绪状态，为后续对话提供情绪上下文。
"""

from typing import Dict, Any
from langgraph.config import get_stream_writer
from modules.logger import log
from .steps import Step


class FeelingNode:
    """情绪检测节点"""

    def __init__(self, feeling_detector: Any):
        """
        初始化情绪检测节点

        Args:
            feeling_detector: 情绪检测器实例，需实现 detect(text, detailed) 方法
        """
        self._detector = feeling_detector

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行情绪检测

        Args:
            state: 当前状态（包含 query）

        Returns:
            更新后的状态（包含 feeling）
        """
        writer = get_stream_writer()
        query = state["query"]

        writer(Step.FEELING_DETECT.started_event(detail=f"分析用户输入：{query[:30]}"))
        log(f"[节点: {Step.FEELING_DETECT.step}] 开始执行，查询: {query[:30]}...", "LangGraph")

        feeling = self._detector.detect(query)
        feeling_name = feeling.get('feeling', 'default')
        feeling_score = feeling.get('score', 5)
        detail = f"检测到情绪：{feeling_name}，强度 {feeling_score}"
        writer(Step.FEELING_DETECT.completed_event(detail=detail))
        log(f"[节点: {Step.FEELING_DETECT.step}] 情绪分析结果: {feeling}", "LangGraph")

        return {"feeling": feeling}
