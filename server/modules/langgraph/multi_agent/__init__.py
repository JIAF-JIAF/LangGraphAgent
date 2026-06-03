"""
多 Agent 协作模块

基于 LangGraph 原生能力 + 自定义精细控制的混合架构。
通过 Feature Flag 控制渐进式迁移，确保旧系统不受影响。
"""

import os


def is_multi_agent_enabled() -> bool:
    """
    是否启用多 Agent 模式（总开关）

    Returns:
        True 表示启用
    """
    return os.getenv("MULTI_AGENT_ENABLED", "false").lower() in ("true", "1", "yes", "on")


def is_agent_enabled(agent_name: str) -> bool:
    """
    是否启用指定 Agent Subgraph（细粒度开关，如 rag_expert、skill_expert）

    Args:
        agent_name: Agent 名称（如 "rag_expert"）

    Returns:
        True 表示启用
    """
    env_key = f"MULTI_AGENT_{agent_name.upper()}_ENABLED"
    return os.getenv(env_key, "false").lower() in ("true", "1", "yes", "on")


def is_parallel_enabled() -> bool:
    """
    是否启用并行执行（Send API）

    Returns:
        True 表示启用
    """
    return os.getenv("MULTI_AGENT_PARALLEL_ENABLED", "false").lower() in ("true", "1", "yes", "on")
