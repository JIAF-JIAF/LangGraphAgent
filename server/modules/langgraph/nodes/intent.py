"""
意图识别和路由节点

负责：
1. 识别用户意图（支持多意图）
2. 根据意图类型决定执行路径
"""

from typing import Dict, Any
from modules.logger import log
from modules.intent import IntentCategory, IntentConstants


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
        query = state["query"]
        query_preview = query[:30] if len(query) > 30 else query
        log(f"[节点: intent_recognize] 开始意图识别: {query_preview}...", "LangGraph")

        if not self._router:
            log(f"[节点: intent_recognize] 未配置意图路由器，跳过意图识别", "LangGraph")
            return {
                "intents": [],
                "is_multi_intent": False,
                "current_intent_idx": 0,
                "current_intent": None,
            }

        intents = self._router.route(query)
        is_multi_intent = len(intents) > 1

        log(f"[节点: intent_recognize] 识别到 {len(intents)} 个意图，是否多意图: {is_multi_intent}", "LangGraph")
        for i, intent in enumerate(intents):
            content_preview = intent.content[:30] if len(intent.content) > 30 else intent.content
            log(f"  [{i+1}] {intent.type}: {content_preview}...", "LangGraph")

        intents_data = [intent.to_dict() for intent in intents]
        current_intent = intents_data[0] if intents_data else None

        return {
            "intents": intents_data,
            "is_multi_intent": is_multi_intent,
            "current_intent_idx": 0,
            "current_intent": current_intent,
        }


class IntentRouterNode:
    """意图路由节点"""

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据意图类型决定执行路径
        
        Args:
            state: 当前状态（包含 intents）
        
        Returns:
            更新后的状态（包含 execution_mode）
        """
        intents = state.get("intents", [])

        # 检查是否有系统指令
        for intent_data in intents:
            category = IntentCategory(intent_data["category"])
            if category == IntentCategory.SYSTEM:
                log(f"[节点: intent_router] 检测到系统指令，走系统模式", "LangGraph")
                return {"execution_mode": "system"}

        # 检查是否有复杂意图
        for intent_data in intents:
            category = IntentCategory(intent_data["category"])
            if category not in IntentConstants.SIMPLE_CATEGORIES:
                log(f"[节点: intent_router] 检测到复杂意图，走规划模式", "LangGraph")
                return {"execution_mode": "plan"}

        # 全部是简单意图
        log(f"[节点: intent_router] 全是简单意图，走直接执行模式", "LangGraph")
        log(f"  意图数量: {len(intents)}", "LangGraph")
        return {"execution_mode": "direct"}
