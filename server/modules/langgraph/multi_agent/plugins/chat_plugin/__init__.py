"""
Chat Expert 插件

处理简单闲聊、问候、简单问答等对话意图，以及系统指令（帮助、退出等）。
"""

from modules.langgraph.multi_agent.plugins.chat_plugin.plugin import ChatPlugin

__all__ = ["ChatPlugin"]
