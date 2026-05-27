"""
回答润色器模块

负责将执行结果润色为自然、友好的回答。
"""

from .base import BaseRefiner, RefineContext
from .refiner_registry import RefinerRegistry
from .intent_refiner import IntentResultRefiner
from .summary_refiner import SummaryRefiner
from .direct_refiner import DirectRefiner

__all__ = [
    "BaseRefiner",
    "RefineContext",
    "RefinerRegistry",
    "IntentResultRefiner",
    "SummaryRefiner",
    "DirectRefiner",
]
