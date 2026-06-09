"""
内置插件包

提供 4 个内置 Expert 插件：MCP、Skill、RAG、Chat。
新增 Expert 只需在 plugins/ 目录下新建子目录（含 PLUGIN.yaml + plugin.py），无需修改框架代码。

Manifest 驱动架构：
  - 每个插件从 PLUGIN.yaml 加载 Manifest
  - routing/prompt/intents 全部声明式，消除硬编码
"""

import os
from modules.langgraph.multi_agent.manifest import load_manifest
from modules.langgraph.multi_agent.plugins.mcp_plugin.plugin import MCPPlugin
from modules.langgraph.multi_agent.plugins.skill_plugin.plugin import SkillPlugin
from modules.langgraph.multi_agent.plugins.rag_plugin.plugin import RAGPlugin
from modules.langgraph.multi_agent.plugins.chat_plugin.plugin import ChatPlugin


def create_builtin_plugins() -> list:
    """
    创建内置插件实例（从 PLUGIN.yaml 加载 Manifest）

    Returns:
        插件实例列表
    """
    plugins_dir = os.path.dirname(__file__)
    plugin_dirs = {
        "mcp_plugin": MCPPlugin,
        "skill_plugin": SkillPlugin,
        "rag_plugin": RAGPlugin,
        "chat_plugin": ChatPlugin,
    }

    plugins = []
    for dir_name, plugin_cls in plugin_dirs.items():
        plugin_dir = os.path.join(plugins_dir, dir_name)
        manifest = load_manifest(plugin_dir)
        if manifest:
            plugins.append(plugin_cls(manifest))
        else:
            # Manifest 加载失败时，使用默认参数创建（向后兼容）
            from modules.langgraph.multi_agent.manifest import PluginManifest, ExpertConfig
            default_manifest = PluginManifest(
                name=f"{dir_name.replace('_plugin', '_expert')}",
                description="",
                expert=ExpertConfig(category=dir_name.replace("_plugin", "")),
            )
            plugins.append(plugin_cls(default_manifest))

    return plugins


__all__ = ["MCPPlugin", "SkillPlugin", "RAGPlugin", "ChatPlugin", "create_builtin_plugins"]
