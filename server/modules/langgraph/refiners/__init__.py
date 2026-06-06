"""
回答润色器模块

负责将执行结果润色为自然、友好的回答。
新架构下由 MergeNode 统一润色，Chat Expert 的 Supervisor 直接调度路径仍使用 RefinerRegistry。
"""

from .base import BaseRefiner, RefineContext
from .refiner_registry import RefinerRegistry
from .chat_refiner import ChatRefiner

# 注册 Chat 润色器（兜底，处理 Chat Expert 的 Supervisor 直接调度路径）
RefinerRegistry.register("chat", ChatRefiner)

__all__ = [
    "BaseRefiner",
    "RefineContext",
    "RefinerRegistry",
    "ChatRefiner",
]
