"""
RAG Expert 插件

处理知识库检索意图。使用领域专精 Agent（只绑定 RAG 工具），
LLM-in-the-loop 自动完成知识库选择、检索和答案生成。
"""

from modules.langgraph.multi_agent.plugins.rag_plugin.plugin import RAGPlugin

__all__ = ["RAGPlugin"]
