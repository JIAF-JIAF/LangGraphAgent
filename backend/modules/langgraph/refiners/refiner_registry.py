"""
润色器注册表（工厂模式）

管理所有润色器，支持注册和构建。
"""

from typing import Dict, Type, Any, List
from modules.logger import log
from .base import BaseRefiner, RefineContext


class RefinerRegistry:
    """
    润色器注册表（工厂类）
    
    管理所有润色器类，新的润色器通过 RefinerRegistry.register() 注册。
    """

    _refiners: Dict[str, Type[BaseRefiner]] = {}

    @classmethod
    def register(cls, name: str, refiner_class: Type[BaseRefiner]) -> None:
        """
        注册润色器类
        
        Args:
            name: 润色器名称，如 "intent_result"、"summary"、"direct"
            refiner_class: 继承自 BaseRefiner 的润色器类
        """
        cls._refiners[name.lower()] = refiner_class
        log(f"[RefinerRegistry] 注册润色器: {name}", "Refiner")

    @classmethod
    def build(cls, name: str, **kwargs) -> BaseRefiner:
        """
        构建润色器实例
        
        Args:
            name: 润色器名称
            **kwargs: 传递给润色器的初始化参数
            
        Returns:
            润色器实例
            
        Raises:
            ValueError: 如果润色器类型不支持
        """
        refiner_class = cls._refiners.get(name.lower())
        if refiner_class is None:
            supported = ", ".join(cls._refiners.keys())
            raise ValueError(f"不支持的润色器类型: {name}，支持的类型: {supported}")
        
        return refiner_class(**kwargs)

    @classmethod
    def get_supported_types(cls) -> list:
        """
        获取支持的润色器类型列表
        
        Returns:
            支持的类型列表
        """
        return list(cls._refiners.keys())

    @classmethod
    def build_all(cls, **kwargs) -> List[BaseRefiner]:
        """
        构建所有润色器实例
        
        Args:
            **kwargs: 传递给润色器的初始化参数
            
        Returns:
            润色器实例列表
        """
        return [
            cls.build(name, **kwargs)
            for name in cls._refiners
        ]

    @classmethod
    def refine(
        cls,
        context: RefineContext,
        agent: Any,
        refiners: List[BaseRefiner],
    ) -> str:
        """
        润色回答
        
        根据上下文选择合适的润色器进行处理。
        
        Args:
            context: 润色上下文
            agent: Agent 实例
            refiners: 润色器实例列表
            
        Returns:
            润色后的回答
        """
        for refiner in refiners:
            if refiner.can_handle(context):
                log(f"[RefinerRegistry] 选择润色器: {refiner.name}", "Refiner")
                return refiner.refine(context, agent)
        
        log(f"[RefinerRegistry] 无匹配润色器，返回空回答", "Refiner")
        return ""
