"""
限流模块
封装 Flask-Limiter，提供可配置的 API 限流功能
支持从环境变量读取配置
"""

import os
from functools import wraps
from typing import Optional, Callable
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()


class RateLimiter:
    """API 限流管理器

    基于 Flask-Limiter 实现，支持从环境变量灵活配置限流规则。
    """

    def __init__(self):
        """初始化限流管理器。"""
        self.limiter: Optional[Limiter] = None
        enabled = os.getenv("RATE_LIMIT_ENABLED")
        self.enabled = enabled is not None and enabled.lower() in ('true', '1', 'yes')

    def _format_limit(self, limit_value) -> Optional[str]:
        """格式化限流规则。

        Args:
            limit_value: 限流值，可以是 int、float 或 str

        Returns:
            格式化后的限流规则字符串
        """
        if isinstance(limit_value, (int, float)):
            return f"{int(limit_value)} per minute"
        return limit_value

    def init_app(self, app: Flask) -> Optional[Limiter]:
        """初始化 Flask 应用的限流功能。

        Args:
            app: Flask 应用实例

        Returns:
            初始化后的 Limiter 实例，限流禁用时返回 None
        """
        if not self.enabled:
            print("限流功能已禁用")
            return None

        storage_uri = os.getenv("RATE_LIMIT_STORAGE_URI") or "memory://"
        key_prefix = os.getenv("RATE_LIMIT_KEY_PREFIX") or "langchain_chatflow"
        default_limit = int(os.getenv("RATE_LIMIT_DEFAULT_LIMIT") or "100")

        self.limiter = Limiter(
            get_remote_address,
            app=app,
            storage_uri=storage_uri,
            key_prefix=key_prefix,
            default_limits=[self._format_limit(default_limit)]
        )

        print(f"限流功能已启用: 默认限制 {default_limit}")
        return self.limiter

    def get_limit(self, limit_name: str) -> Optional[str]:
        """获取指定名称的限流规则。

        Args:
            limit_name: 限流规则名称，如 "chat_limit"、"start_limit"

        Returns:
            格式化后的限流规则字符串，限流禁用时返回 None
        """
        if not self.enabled:
            return None
        limit_key = f"RATE_LIMIT_{limit_name.upper()}"
        limit_value = int(os.getenv(limit_key) or "100")
        return self._format_limit(limit_value)

    def limit(self, limit_name: str) -> Callable:
        """限流装饰器工厂函数。

        Args:
            limit_name: 限流规则名称，对应配置文件中的键名

        Returns:
            装饰器函数
        """
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not self.enabled or not self.limiter:
                    return f(*args, **kwargs)

                limit = self.get_limit(limit_name)
                if not limit:
                    return f(*args, **kwargs)

                return self.limiter.limit(limit)(f)(*args, **kwargs)
            return decorated_function
        return decorator


__all__ = ['RateLimiter']
