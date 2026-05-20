"""
上下文管理模块

提供线程/协程安全的上下文传递机制，用于主服务与 MCP 服务之间的参数传递。
"""

import contextvars
from typing import Any

_service_context: contextvars.ContextVar[dict] = contextvars.ContextVar(
    'SERVICE_CONTEXT', default={}
)


def set_value(key: str, value: Any) -> None:
    """设置上下文值"""
    ctx = _service_context.get().copy()
    ctx[key] = value
    _service_context.set(ctx)


def get_value(key: str, default: Any = None) -> Any:
    """获取上下文值"""
    return _service_context.get().get(key, default)


def remove_value(key: str) -> None:
    """移除上下文值"""
    ctx = _service_context.get().copy()
    ctx.pop(key, None)
    _service_context.set(ctx)


def clear() -> None:
    """清空上下文"""
    _service_context.set({})