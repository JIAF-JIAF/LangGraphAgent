"""
内置插件包

提供 4 个内置 Expert 插件：MCP、Skill、RAG、Chat。
新增 Expert 只需在 plugins/ 目录下新建文件，无需修改框架代码。
"""

from modules.langgraph.multi_agent.plugins.mcp_plugin import MCPPlugin
from modules.langgraph.multi_agent.plugins.skill_plugin import SkillPlugin
from modules.langgraph.multi_agent.plugins.rag_plugin import RAGPlugin
from modules.langgraph.multi_agent.plugins.chat_plugin import ChatPlugin

__all__ = ["MCPPlugin", "SkillPlugin", "RAGPlugin", "ChatPlugin"]
