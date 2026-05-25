"""
意图识别模块

提供多意图识别和路由能力，解决用户请求包含多个意图的问题。

业界 2026 年标准架构：
- 分层漏斗路由：L1 关键词 → L2 向量 → L3 大模型 FC
- 动态意图类型：从 MCP + Skill + RAG 自动注册
- 多意图支持：识别并拆分多意图请求

核心组件：
- Intent: 意图对象
- IntentCategory: 意图类别
- IntentRegistry: 意图注册表（动态管理意图类型）
- IntentRecognizer: LLM 意图识别器
- IntentRouter: 分层漏斗路由器
"""

from .intent_types import Intent, IntentCategory, IntentConstants
from .intent_registry import IntentRegistry
from .recognizer import IntentRecognizer
from .router import IntentRouter

__all__ = [
    "Intent",
    "IntentCategory",
    "IntentConstants",
    "IntentRegistry",
    "IntentRecognizer",
    "IntentRouter",
]
