"""
意图类型定义

定义意图对象和基础意图类型。
意图类型不是硬编码，而是从可用工具（MCP + Skill + RAG）动态获取。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


class IntentCategory(Enum):
    """
    意图类别枚举
    
    意图分为以下类别：
    - MCP: MCP 工具调用
    - SKILL: 技能执行
    - RAG: 知识库检索
    - CHAT: 普通对话（闲聊、问候、感谢等）
    - SYSTEM: 系统指令（帮助、退出等）
    """
    
    MCP = "mcp"
    SKILL = "skill"
    RAG = "rag"
    CHAT = "chat"
    SYSTEM = "system"


@dataclass
class Intent:
    """
    意图对象
    
    表示用户请求中的一个独立意图。
    
    Attributes:
        type: 意图类型（如 mcp_weather, skill_drawio, rag_exams）
        category: 意图类别
        content: 意图具体内容
        target: 目标处理器（如 skill:drawio-skill, knowledge_base:exams）
        order: 执行顺序（从1开始）
        confidence: 置信度（0-1）
        metadata: 额外元数据
    """
    
    type: str
    category: IntentCategory
    content: str
    target: str
    order: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "category": self.category.value,
            "content": self.content,
            "target": self.target,
            "order": self.order,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Intent":
        """从字典创建"""
        return cls(
            type=data["type"],
            category=IntentCategory(data.get("category", "system")),
            content=data["content"],
            target=data.get("target", ""),
            order=data["order"],
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
        )
    
    def get_handler_node(self) -> str:
        """
        获取处理该意图的 LangGraph 节点名称
        
        Returns:
            节点名称
        """
        if self.category == IntentCategory.RAG:
            return "retrieve"
        elif self.category == IntentCategory.SKILL:
            return "skill_executor"
        elif self.category == IntentCategory.MCP:
            return "mcp_executor"
        else:
            return "call_model"


class IntentConstants:
    """意图相关常量"""
    
    MULTI_INTENT_CONNECTORS = [
        "先", "再", "然后", "接着", "之后", "同时",
        "首先", "其次", "最后", "并且", "以及", "另外",
    ]
    
    SYSTEM_INTENTS = {
        "system_help": "帮助",
        "system_exit": "退出",
        "system_confirm": "确认",
        "system_cancel": "取消",
    }
    
    CHAT_INTENTS = {
        "general_chat": "通用对话，处理闲聊、问候、感谢等日常对话",
    }
    
    SIMPLE_CATEGORIES = {
        IntentCategory.RAG, 
        IntentCategory.SKILL, 
        IntentCategory.MCP,
        IntentCategory.CHAT,
    }
