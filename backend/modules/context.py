"""
Agent 上下文类

统一管理 Agent 执行所需的所有上下文信息，避免参数爆炸问题。
参考 2026 年 LangChain Context Engineering 最佳实践。
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage


class AgentContext(BaseModel):
    """
    Agent 执行上下文
    
    包含所有 Agent 执行所需的上下文信息，分为以下几类：
    
    1. 用户信息 (User Context)
    2. 会话信息 (Session Context)
    3. 执行上下文 (Execution Context)
    4. 运行时配置 (Runtime Config)
    
    参考：https://docs.langchain.com/oss/python/langchain/context-engineering
    """
    
    # ========== 用户信息 ==========
    user_id: Optional[str] = Field(
        None, 
        description="用户唯一标识，用于权限验证和个性化"
    )
    
    # ========== 会话信息 ==========
    session_id: str = Field(
        "default", 
        description="会话 ID，用于维护对话状态"
    )
    
    chat_history: List[BaseMessage] = Field(
        default_factory=list,
        description="对话历史记录（LangChain 消息对象）"
    )
    
    # ========== 执行上下文 ==========
    skill_name: str = Field(
        "", 
        description="当前正在执行的技能名称"
    )
    
    feeling: Dict[str, Any] = Field(
        default_factory=dict, 
        description="情绪状态，格式: {'feeling': str, 'score': int}"
    )
    
    # ========== 运行时配置 ==========
    runtime_config: Dict[str, Any] = Field(
        default_factory=dict, 
        description="运行时配置，如超时时间、模型参数等"
    )
    
    def get_feeling(self) -> Dict[str, Any]:
        """获取情绪状态，提供默认值"""
        return self.feeling or {"feeling": "default", "score": 5}
    
    def get_score(self) -> int:
        """获取情绪分数"""
        return self.get_feeling().get("score", 5)
