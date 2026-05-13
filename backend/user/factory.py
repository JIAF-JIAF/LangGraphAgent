"""
UserStore 工厂类

管理所有可用的用户存储实现，支持注册和构建。

核心功能：
- 注册用户存储类
- 根据名称构建存储实例
- 获取支持的存储类型列表
"""

import os
from typing import Dict, Type, Optional, Any

from .base import BaseUserStore


class UserStoreFactory:
    """
    用户存储工厂类
    
    管理所有可用的用户存储实现，新的存储实现通过 UserStoreFactory.register() 注册。
    """

    _stores: Dict[str, Type[BaseUserStore]] = {}

    @classmethod
    def register(cls, name: str, store_class: Type[BaseUserStore]) -> None:
        """
        注册用户存储类
        
        Args:
            name: 存储类型名称，如 "memory"、"redis"
            store_class: 继承自 BaseUserStore 的存储类
        """
        cls._stores[name.lower()] = store_class

    @classmethod
    def build(cls, name: Optional[str] = None, **kwargs) -> BaseUserStore:
        """
        构建用户存储实例
        
        Args:
            name: 存储类型名称，如 "memory"、"redis"。默认为 None，从环境变量获取
            **kwargs: 传递给存储类的初始化参数
            
        Returns:
            对应的用户存储实例
            
        Raises:
            ValueError: 如果存储类型不支持
        """
        if name is None:
            name = os.getenv("USER_STORAGE", "memory").lower()

        store_class = cls._stores.get(name)
        if store_class is None:
            supported_types = ", ".join(cls._stores.keys())
            raise ValueError(f"不支持的用户存储类型: {name}，支持的类型: {supported_types}")

        return store_class.build(**kwargs) if hasattr(store_class, 'build') else store_class(**kwargs)

    @classmethod
    def get_supported_types(cls) -> list:
        """
        获取支持的用户存储类型列表
        
        Returns:
            支持的类型列表
        """
        return list(cls._stores.keys())


__all__ = ['UserStoreFactory']
