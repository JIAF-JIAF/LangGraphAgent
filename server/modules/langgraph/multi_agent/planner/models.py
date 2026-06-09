"""
Planner 数据模型

定义任务分解的 Pydantic 结构化输出模型和常量。
独立于分解逻辑，避免循环导入。

Manifest 驱动：PlannedSubtask 的 category/targets Field 描述
由 build_planned_subtask_model() 运行时动态生成，
新增 Expert 无需修改此文件。
"""

from typing import List
from pydantic import BaseModel, Field, create_model


# ==================== Pydantic 结构化输出模型 ====================

class PlannedSubtask(BaseModel):
    """
    单个规划子任务（默认模型）

    实际使用时，建议通过 build_planned_subtask_model() 动态生成，
    以注入当前注册插件的类别和 target 格式描述。

    Attributes:
        description: 子任务描述，包含足够信息让 Expert 独立执行
        category: 目标 Expert 类别
        depends_on: 依赖的子任务索引列表（0-based），空列表表示可立即执行
        targets: 目标标识列表
    """
    description: str = Field(description="子任务描述，包含足够信息让 Expert 独立执行")
    category: str = Field(description="目标 Expert 类别")
    depends_on: List[int] = Field(
        default_factory=list,
        description="依赖的子任务索引（0-based），空列表表示可立即执行。"
                    "如果子任务 B 需要子任务 A 的结果，则 B 的 depends_on 包含 A 的索引"
    )
    targets: List[str] = Field(
        default_factory=list,
        description='目标标识列表'
    )


def build_planned_subtask_model(category_options: str, target_format_descriptions: str) -> type:
    """
    动态构建 PlannedSubtask 模型（注入 Manifest 驱动的 Field 描述）

    替代硬编码的 Field 描述：
      category: "目标 Expert 类别：mcp、skill、rag 或 chat"
      targets: "skill 类别填 [...], mcp 类别填 [...]"

    Args:
        category_options: 类别选项文本，如 "mcp、skill、rag 或 chat"
        target_format_descriptions: target 格式描述文本

    Returns:
        动态生成的 PlannedSubtask 子类
    """
    return create_model(
        "PlannedSubtask",
        description=(str, Field(description="子任务描述，包含足够信息让 Expert 独立执行")),
        category=(str, Field(description=f"目标 Expert 类别：{category_options}")),
        depends_on=(List[int], Field(
            default_factory=list,
            description="依赖的子任务索引（0-based），空列表表示可立即执行。"
                        "如果子任务 B 需要子任务 A 的结果，则 B 的 depends_on 包含 A 的索引"
        )),
        targets=(List[str], Field(
            default_factory=list,
            description=f"目标标识列表。{target_format_descriptions}"
        )),
    )


def build_task_decomposition_model(category_options: str, target_format_descriptions: str) -> type:
    """
    动态构建 TaskDecomposition 模型

    Args:
        category_options: 类别选项文本
        target_format_descriptions: target 格式描述文本

    Returns:
        动态生成的 TaskDecomposition 子类
    """
    subtask_model = build_planned_subtask_model(category_options, target_format_descriptions)

    return create_model(
        "TaskDecomposition",
        subtasks=(List[subtask_model], Field(description="子任务列表，按逻辑顺序排列")),
        reasoning=(str, Field(default="", description="分解理由")),
        difficulty=(int, Field(default=3, description="任务难度等级（1-5）")),
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
