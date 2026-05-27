"""
回答润色器基类

定义润色器的统一接口，支持不同场景的回答润色。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class RefineContext:
    """
    润色上下文数据结构
    
    Attributes:
        query: 用户查询
        feeling: 情绪状态
        chat_history: 对话历史
        intent_results: 意图执行结果（direct 路径）
        answer: 汇总结果（plan 路径）
    """
    query: str
    feeling: Dict[str, Any]
    chat_history: List[Any]
    intent_results: List[Dict[str, Any]]
    answer: str
    
    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> "RefineContext":
        """
        从状态创建润色上下文
        
        Args:
            state: Agent 状态
            
        Returns:
            润色上下文实例
        """
        return cls(
            query=state.get("query", ""),
            feeling=state.get("feeling", {}),
            chat_history=state.get("chat_history", []),
            intent_results=state.get("intent_results", []),
            answer=state.get("answer", ""),
        )


class BaseRefiner(ABC):
    """
    回答润色器抽象基类
    
    所有具体润色器都需要继承此类并实现 refine 方法。
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        润色器名称
        
        Returns:
            名称字符串
        """
        pass
    
    @abstractmethod
    def can_handle(self, context: RefineContext) -> bool:
        """
        判断是否能处理该上下文
        
        Args:
            context: 润色上下文
            
        Returns:
            是否能处理
        """
        pass
    
    @abstractmethod
    def refine(self, context: RefineContext, agent: Any) -> str:
        """
        润色回答
        
        Args:
            context: 润色上下文
            agent: Agent 实例
            
        Returns:
            润色后的回答
        """
        pass
    
    def build_prompt(
        self,
        query: str,
        content: str,
        feeling: Dict[str, Any],
        content_label: str = "执行结果",
    ) -> str:
        """
        构建润色 Prompt
        
        Args:
            query: 用户查询
            content: 待润色内容
            feeling: 情绪状态
            content_label: 内容标签
            
        Returns:
            润色 Prompt
        """
        feeling_name = feeling.get("feeling", "neutral")
        feeling_score = feeling.get("score", 5)
        
        return f"""请根据以下信息，结合用户的情绪状态，生成一个自然、友好的回复：

        用户查询：{query}

        {content_label}：
        {content}

        用户情绪：{feeling_name}（强度：{feeling_score}）

        请将{content_label}用自然的语言组织成回复，注意语气要符合用户情绪。
        """
