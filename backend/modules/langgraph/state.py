"""
LangGraph 状态定义

定义 Agent 执行过程中需要追踪的所有状态信息，支持复杂任务规划和反思校验。
"""

from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    Agent 状态定义
    
    包含对话管理、任务规划、反思校验、技能匹配所需的所有状态字段。
    """
    
    # ========== 基础字段 ==========
    query: str  # 用户查询
    session_id: str  # 会话 ID
    chat_history: List[BaseMessage]  # 对话历史（统一管理）
    need_retrieve: bool  # 是否需要检索
    documents: List[Document]  # 检索到的文档
    answer: str  # 生成的回答
    feeling: Dict[str, Any]  # 用户情绪状态 {"feeling": str, "score": int}
    uid: Optional[str]  # 用户 ID（用于钉钉等外部工具调用）
    
    # ========== 技能匹配字段 ==========
    matched_skill: Optional[Dict[str, Any]]  # 匹配到的技能定义
    skill_executed: bool  # 技能是否已执行
    skill_name: str  # 执行的技能名称
    skill_success: bool  # 技能执行是否成功
    skill_steps: List[Dict[str, Any]]  # 技能执行步骤结果
    
    # ========== 任务规划字段 ==========
    subtasks: List[Dict[str, Any]]  # 子任务队列
    # 每个子任务结构：
    # {
    #     "task_id": str,           # 任务唯一标识
    #     "task_description": str,   # 任务描述
    #     "dependencies": List[str], # 依赖的前置任务ID列表
    #     "status": str,             # 任务状态（pending/completed/failed）
    #     "result": str              # 任务执行结果
    # }
    
    current_task_idx: int  # 当前执行的子任务索引
    is_task_completed: bool  # 当前任务是否已完成
    
    # ========== 反思校验字段 ==========
    is_reflection_passed: bool  # 反思校验是否通过
    reflection_feedback: str  # 反思校验反馈信息
    reflection_suggestions: List[str]  # 改进建议列表
    reflection_confidence: float  # 置信度评分
    
    # ========== 重试控制字段 ==========
    retry_count: int  # 当前重试次数
    max_retries: int  # 最大重试次数（默认3次）
    retry_task_idx: int  # 需要重试的任务索引（用于定位失败任务）
