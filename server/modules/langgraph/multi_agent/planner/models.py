"""
Planner 数据模型

定义任务分解的 Pydantic 结构化输出模型和常量。
独立于分解逻辑，避免循环导入。
"""

from typing import List
from pydantic import BaseModel, Field


# ==================== Pydantic 结构化输出模型 ====================

class PlannedSubtask(BaseModel):
    """
    单个规划子任务

    Attributes:
        description: 子任务描述，包含足够信息让 Expert 独立执行
        category: 目标 Expert 类别（mcp / skill / rag / chat）
        depends_on: 依赖的子任务索引列表（0-based），空列表表示可立即执行
        targets: 目标标识列表，格式为 "类别前缀:具体ID"
    """
    description: str = Field(description="子任务描述，包含足够信息让 Expert 独立执行")
    category: str = Field(description="目标 Expert 类别：mcp、skill、rag 或 chat")
    depends_on: List[int] = Field(
        default_factory=list,
        description="依赖的子任务索引（0-based），空列表表示可立即执行。"
                    "如果子任务 B 需要子任务 A 的结果，则 B 的 depends_on 包含 A 的索引"
    )
    targets: List[str] = Field(
        default_factory=list,
        description='目标标识列表，格式为 "类别前缀:具体ID"。'
                    'skill 类别填 ["skill:技能ID"]（如 ["skill:drawio-skill"]），'
                    'mcp 类别填 ["mcp:工具名"]（如 ["mcp:get_weather"]），'
                    'rag 类别填 ["knowledge_base:知识库名"]（如 ["knowledge_base:exams"]），'
                    'chat 类别留空 []'
    )


class TaskDecomposition(BaseModel):
    """
    任务分解结果（结构化输出）

    Attributes:
        subtasks: 子任务列表，按逻辑顺序排列
        reasoning: 分解理由（用于日志和调试）
        difficulty: 任务难度等级（1-5）
    """
    subtasks: List[PlannedSubtask] = Field(description="子任务列表，按逻辑顺序排列")
    reasoning: str = Field(default="", description="分解理由")
    difficulty: int = Field(default=3, description="任务难度等级（1-5）")


# ==================== 意图分类常量 ====================

# 可执行类别由 PluginRegistry.build_executable_categories() 动态生成，
# 新增插件时自动包含，无需手动维护此列表。

# 复杂规划意图类别（系统级常量，不属于插件）
COMPLEX_PLAN_CATEGORY = "complex_plan"
