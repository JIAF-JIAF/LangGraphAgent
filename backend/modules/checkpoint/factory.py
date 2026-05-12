"""
检查点存储工厂类

管理所有可用的检查点存储实现，支持注册和构建。

核心功能：
- 注册检查点存储类
- 根据名称构建存储实例
- 获取支持的存储类型列表
"""

import os
from typing import Dict, Type, Optional, Any
from langgraph.checkpoint.base import BaseCheckpointSaver


class CheckpointFactory:
    """
    检查点存储工厂类
    
    管理所有可用的检查点存储实现，新的存储实现通过 CheckpointFactory.register() 注册。
    """

    _savers: Dict[str, Type[BaseCheckpointSaver]] = {}

    @classmethod
    def register(cls, name: str, saver_class: Type[BaseCheckpointSaver]) -> None:
        """
        注册检查点存储类
        
        Args:
            name: 存储类型名称，如 "memory"、"redis"
            saver_class: 继承自 BaseCheckpointSaver 的存储类
        """
        cls._savers[name.lower()] = saver_class

    @classmethod
    def build(cls, name: Optional[str] = None, **kwargs) -> BaseCheckpointSaver:
        """
        构建检查点存储实例
        
        Args:
            name: 存储类型名称，如 "memory"、"redis"。默认为 None，从环境变量获取
            **kwargs: 传递给存储类的初始化参数
            
        Returns:
            对应的检查点存储实例
            
        Raises:
            ValueError: 如果存储类型不支持
        """
        if name is None:
            name = os.getenv("CHECKPOINT_STORAGE", "memory").lower()

        saver_class = cls._savers.get(name)
        if saver_class is None:
            supported_types = ", ".join(cls._savers.keys())
            raise ValueError(f"不支持的检查点存储类型: {name}，支持的类型: {supported_types}")

        return saver_class.build(**kwargs) if hasattr(saver_class, 'build') else saver_class(**kwargs)

    @classmethod
    def get_supported_types(cls) -> list:
        """
        获取支持的检查点存储类型列表
        
        Returns:
            支持的类型列表
        """
        return list(cls._savers.keys())


__all__ = ['CheckpointFactory']
