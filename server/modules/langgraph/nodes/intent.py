"""
意图识别节点

负责识别用户意图（支持多意图），为 Supervisor 路由提供意图信息。
"""

from typing import Dict, Any
from langgraph.config import get_stream_writer
from modules.logger import log
from .steps import Step


class IntentRecognizeNode:
    """意图识别节点"""

    def __init__(self, intent_router: Any):
        """
        初始化意图识别节点

        Args:
            intent_router: 意图路由器实例
        """
        self._router = intent_router

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行意图识别

        Args:
            state: 当前状态（包含 query）

        Returns:
            更新后的状态（包含 intents, is_multi_intent, current_intent）
        """
        writer = get_stream_writer()
        query = state["query"]
        query_preview = query[:30] if len(query) > 30 else query

        writer(Step.INTENT_RECOGNIZE.started_event(detail=f"识别用户意图：{query_preview}"))
        writer(Step.INTENT_RECOGNIZE.progress_event(detail="正在分析用户意图..."))
        log(f"[节点: {Step.INTENT_RECOGNIZE.step}] 开始意图识别: {query_preview}...", "LangGraph")

        if not self._router:
            log(f"[节点: {Step.INTENT_RECOGNIZE.step}] 未配置意图路由器，跳过意图识别", "LangGraph")
            writer(Step.INTENT_RECOGNIZE.completed_event(detail="跳过（无路由器）"))
            return {
                "intents": [],
                "is_multi_intent": False,
                "current_intent_idx": 0,
                "current_intent": None,
            }

        intents = self._router.route(query)
        is_multi_intent = len(intents) > 1

        log(f"[节点: {Step.INTENT_RECOGNIZE.step}] 识别到 {len(intents)} 个意图，是否多意图: {is_multi_intent}", "LangGraph")
        for i, intent in enumerate(intents):
            content_preview = intent.content[:30] if len(intent.content) > 30 else intent.content
            log(f"  [{i+1}] {intent.type}: {content_preview}...", "LangGraph")

        intents_data = [intent.to_dict() for intent in intents]
        current_intent = intents_data[0] if intents_data else None

        intent_desc = "、".join(
            f"{i.get('type', '?')}({i.get('content', '')[:20]})"
            for i in intents_data
        ) if intents_data else "无匹配意图"
        writer(Step.INTENT_RECOGNIZE.completed_event(detail=intent_desc))

        return {
            "intents": intents_data,
            "is_multi_intent": is_multi_intent,
            "current_intent_idx": 0,
            "current_intent": current_intent,
        }
