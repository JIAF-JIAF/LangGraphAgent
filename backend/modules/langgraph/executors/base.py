"""
意图执行器基类

定义执行器的统一接口，支持不同类型意图的执行。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """
    执行结果数据结构
    
    Attributes:
        success: 是否执行成功
        content: 执行结果内容
        error: 错误信息（如果有）
        metadata: 额外元数据
    """
    success: bool
    content: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseExecutor(ABC):
    """
    意图执行器抽象基类
    
    所有具体执行器（RAG/Skill/MCP）都需要继承此类并实现 execute 方法。
    """
    
    @property
    @abstractmethod
    def category(self) -> str:
        """
        执行器对应的意图类别
        
        Returns:
            意图类别字符串（rag/skill/mcp）
        """
        pass
    
    @abstractmethod
    def execute(
        self,
        intent: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """
        执行意图
        
        Args:
            intent: 意图数据（包含 type, category, target, content）
            context: 执行上下文（包含 query, feeling, chat_history 等）
            
        Returns:
            执行结果
        """
        pass
    
    def validate_intent(self, intent: Dict[str, Any]) -> bool:
        """
        验证意图数据是否有效
        
        Args:
            intent: 意图数据
            
        Returns:
            是否有效
        """
        required_fields = ["type", "category", "target", "content"]
        return all(field in intent for field in required_fields)
