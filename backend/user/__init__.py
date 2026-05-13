"""
用户存储模块

提供可替换的用户存储实现：
- BaseUserStore: 基类接口
- MemoryUserStore: 内存存储（默认，不持久化）
- RedisUserStore: Redis 存储（持久化）
- UserStoreFactory: 工厂类，用于构建用户存储实例

用于在钉钉聊天时存储用户信息。

Example:
    >>> from modules.user import UserStoreFactory
    >>> user_store = UserStoreFactory.build()
    >>> user_store.add_user("user123", {"name": "张三", "department": "技术部"})
    >>> user = user_store.get_user("user123")
    >>> print(user)
    {'name': '张三', 'department': '技术部'}
"""

from .base import BaseUserStore
from .memory import MemoryUserStore
from .redis import RedisUserStore
from .factory import UserStoreFactory

__all__ = ["BaseUserStore", "MemoryUserStore", "RedisUserStore", "UserStoreFactory"]
