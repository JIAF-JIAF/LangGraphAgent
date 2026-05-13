"""
内存用户存储实现

使用内存字典存储用户数据，适合开发测试环境。
注意：重启服务后数据会丢失，生产环境建议使用 Redis 或数据库存储。
"""

from typing import Optional, Dict, Any, List

from .base import BaseUserStore


class MemoryUserStore(BaseUserStore):
    """
    内存用户存储

    使用内存字典存储用户数据，特点：
    - 无需外部依赖
    - 读写速度快
    - 重启后数据丢失
    - 适合开发测试环境

    Example:
        >>> from modules.user import MemoryUserStore
        >>> user_store = MemoryUserStore()
        >>> user_store.add_user("user123", {"name": "张三", "department": "技术部"})
        >>> user_store.get_user("user123")
        {'name': '张三', 'department': '技术部'}
    """

    def __init__(self):
        """初始化内存存储"""
        self._store: Dict[str, Dict[str, Any]] = {}

    def add_user(self, user_id: str, user_data: Dict[str, Any]) -> None:
        """
        添加用户

        Args:
            user_id: 用户唯一标识
            user_data: 用户数据字典
        """
        self._store[user_id] = user_data

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户

        Args:
            user_id: 用户唯一标识

        Returns:
            用户数据字典，如果不存在返回 None
        """
        return self._store.get(user_id)

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """
        更新用户数据

        Args:
            user_id: 用户唯一标识
            user_data: 要更新的用户数据（会合并到现有数据）

        Returns:
            如果更新成功返回 True，否则返回 False
        """
        if user_id in self._store:
            self._store[user_id].update(user_data)
            return True
        return False

    def delete_user(self, user_id: str) -> bool:
        """
        删除用户

        Args:
            user_id: 用户唯一标识

        Returns:
            如果删除成功返回 True，否则返回 False
        """
        if user_id in self._store:
            del self._store[user_id]
            return True
        return False

    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有用户

        Returns:
            所有用户数据字典，key 为 user_id
        """
        return self._store.copy()

    def clear(self) -> None:
        """清空所有用户数据"""
        self._store.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            统计信息字典
        """
        return {
            "total_users": len(self._store),
            "storage_type": "memory"
        }

    @classmethod
    def build(cls, **kwargs) -> "MemoryUserStore":
        """
        构建 MemoryUserStore 实例

        Returns:
            MemoryUserStore 实例
        """
        return cls()


from modules.user.factory import UserStoreFactory
UserStoreFactory.register("memory", MemoryUserStore)
