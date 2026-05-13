"""
Redis 用户存储实现

使用 Redis 存储用户数据，适合生产环境。
支持持久化存储，重启服务后数据不会丢失。

依赖：redis 库
"""

import os
import pickle
import redis
from typing import Optional, Dict, Any, List

from .base import BaseUserStore


class RedisUserStore(BaseUserStore):
    """
    Redis 用户存储

    使用 Redis 存储用户数据，特点：
    - 需要 Redis 服务
    - 数据持久化，重启后不丢失
    - 支持分布式部署
    - 适合生产环境

    Example:
        >>> from modules.user import RedisUserStore
        >>> user_store = RedisUserStore(host='localhost', port=6379, db=0)
        >>> user_store.add_user("user123", {"name": "张三"})
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "user:",
        ttl: Optional[int] = None,
    ):
        """
        初始化 Redis 存储

        Args:
            host: Redis 服务器地址
            port: Redis 端口
            db: Redis 数据库编号
            password: Redis 密码（可选）
            prefix: 键名前缀
            ttl: 用户数据过期时间（秒），None 表示永不过期
        """
        self._redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False,
        )
        self._redis.ping()

        self._prefix = prefix
        self._ttl = ttl

    def _get_key(self, user_id: str) -> str:
        """生成用户存储键"""
        return f"{self._prefix}{user_id}"

    def _serialize(self, data: Any) -> bytes:
        """序列化数据"""
        return pickle.dumps(data)

    def _deserialize(self, data: bytes) -> Any:
        """反序列化数据"""
        return pickle.loads(data)

    def add_user(self, user_id: str, user_data: Dict[str, Any]) -> None:
        """
        添加用户

        Args:
            user_id: 用户唯一标识
            user_data: 用户数据字典
        """
        key = self._get_key(user_id)
        serialized_data = self._serialize(user_data)
        self._redis.set(key, serialized_data)

        if self._ttl:
            self._redis.expire(key, self._ttl)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户

        Args:
            user_id: 用户唯一标识

        Returns:
            用户数据字典，如果不存在返回 None
        """
        key = self._get_key(user_id)
        data = self._redis.get(key)
        if data:
            return self._deserialize(data)
        return None

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """
        更新用户数据

        Args:
            user_id: 用户唯一标识
            user_data: 要更新的用户数据（会合并到现有数据）

        Returns:
            如果更新成功返回 True，否则返回 False
        """
        existing_data = self.get_user(user_id)
        if existing_data:
            existing_data.update(user_data)
            self.add_user(user_id, existing_data)
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
        key = self._get_key(user_id)
        result = self._redis.delete(key)
        return result > 0

    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有用户

        Returns:
            所有用户数据字典，key 为 user_id
        """
        pattern = f"{self._prefix}*"
        keys = self._redis.keys(pattern)

        users = {}
        for key in keys:
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            user_id = key_str[len(self._prefix):]
            data = self._redis.get(key)
            if data:
                users[user_id] = self._deserialize(data)

        return users

    def get_user_ids(self) -> List[str]:
        """
        获取所有用户 ID

        Returns:
            用户 ID 列表
        """
        pattern = f"{self._prefix}*"
        keys = self._redis.keys(pattern)

        user_ids = []
        for key in keys:
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            user_id = key_str[len(self._prefix):]
            user_ids.append(user_id)

        return user_ids

    def clear(self) -> None:
        """清空所有用户数据"""
        pattern = f"{self._prefix}*"
        keys = self._redis.keys(pattern)
        if keys:
            self._redis.delete(*keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            统计信息字典
        """
        pattern = f"{self._prefix}*"
        keys = self._redis.keys(pattern)

        return {
            "total_users": len(keys),
            "storage_type": "redis"
        }

    def close(self):
        """关闭 Redis 连接"""
        self._redis.close()

    @classmethod
    def build(cls, **kwargs) -> "RedisUserStore":
        """
        构建 RedisUserStore 实例

        从环境变量获取 Redis 配置参数

        Returns:
            RedisUserStore 实例
        """
        host = kwargs.get("host") or os.getenv("REDIS_HOST", "localhost")
        port = kwargs.get("port") or int(os.getenv("REDIS_PORT", 6379))
        db = kwargs.get("db") or int(os.getenv("REDIS_DB", 0))
        password = kwargs.get("password") or os.getenv("REDIS_PASSWORD")

        return cls(
            host=host,
            port=port,
            db=db,
            password=password,
        )


from modules.user.factory import UserStoreFactory
UserStoreFactory.register("redis", RedisUserStore)
