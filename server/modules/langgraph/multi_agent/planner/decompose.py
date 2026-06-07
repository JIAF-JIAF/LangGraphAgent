"""
Planner 分解节点（统一路由入口）

所有意图统一进入 Planner，由 Planner 内部区分处理：
  - 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务，不调 LLM
  - complex_plan 意图 → LLM 独立分解，保留完整规划能力
  - 混合意图 → 两者合并，波次调度

核心设计：
  - 结构化输出：使用 llm.with_structured_output(TaskDecomposition) 强制约束输出格式
  - 依赖感知：子任务可声明 depends_on，支持跨 Expert 串行依赖
  - 图编排层并行：独立子任务由 Send API 并行分发，依赖子任务按波次执行
  - 独立分解：每个 complex_plan 意图独立调用 LLM 分解，保证分解质量不受上下文干扰

执行流程：
  supervisor → planner_decompose → planner_dispatch ──→ Send(expert) ──→ planner_dispatch (循环)
                                                              ↓ (全部完成)
                                                            merge → END
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.langgraph.nodes.steps import Step


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


# ==================== 分解 Prompt ====================

DECOMPOSE_PROMPT = """你是一个任务分解专家。请将用户的复杂请求分解为独立的子任务，每个子任务分配给合适的专家类别。

可用专家类别及其当前能力：
{capability_descriptions}

分解规则：
1. 每个子任务应包含足够信息让对应专家独立执行
2. 如果子任务 B 依赖子任务 A 的结果，在 B 的 depends_on 中填写 A 的索引（0-based）
3. 如果子任务之间没有依赖关系，depends_on 设为空列表，它们将被并行执行
4. 如果子任务 B 依赖子任务 A，且 A 和 B 属于不同类别，必须拆分为两个子任务并声明依赖
5. 如果子任务 A 和 B 属于同一类别且有依赖，合并为一个子任务（该 Expert 内部会串行处理）
6. 不要过度分解，每个子任务应该是有意义的独立工作单元
7. depends_on 中的索引是相对于本次分解结果的索引（从 0 开始），不要引用已有的子任务
8. 严格对照上方"当前可用工具/技能/知识库"列表，只有列表中明确列出的能力才能分配到对应类别；不在列表中的需求必须归为 chat
9. 评估任务难度：简单查询为1级（1个任务），需要推理为2级（1个任务），多步骤为3级（2个任务），跨领域为4级（3个任务），创造性方案为5级（4个任务）

⚠️ 关键：targets 字段填写规则
- 每个子任务必须填写 targets 列表，用于精准路由到对应的工具/技能/知识库
- skill 类别 → ["skill:技能ID"]（如 ["skill:drawio-skill"]），技能ID 必须是上方"当前可用技能"列表中的 ID
- mcp 类别 → ["mcp:工具名"]（如 ["mcp:get_weather"]），工具名必须是上方"当前可用工具"列表中的名称
- rag 类别 → ["knowledge_base:知识库名"]（如 ["knowledge_base:exams"]），知识库名必须是上方"当前可用知识库"列表中的名称
- chat 类别 → 留空 []
- ⚠️ targets 中的 ID 必须与上方列表完全一致，不要编造不存在的 ID

⚠️ 关键：chat 子任务的拆分规则
- chat 子任务必须按逻辑步骤拆分，不要把整个需求归为一个 chat 子任务
- 例如"创建在线表格应用"应拆分为：
  1. chat: 分析在线表格应用的核心功能需求和架构设计
  2. chat: 设计数据模型和 Excel 兼容功能的实现方案
  3. chat: 规划前后端技术选型和协作功能方案
  4. chat: 整合所有方案，输出完整的开发计划
- 例如"设计方案"应拆分为：
  1. chat: 分析需求并梳理关键约束
  2. chat: 设计核心架构和模块划分
  3. chat: 输出完整方案文档
- 禁止将整个 complex_plan 需求归为单个 chat 子任务（至少拆分为2个以上子任务）

请以 json 格式输出分解结果，格式如下：
{{
  "reasoning": "分解理由，包含难度评估",
  "difficulty": 1-5,
  "subtasks": [
    {{
      "description": "子任务描述",
      "category": "mcp/skill/rag/chat",
      "depends_on": [],
      "targets": ["skill:drawio-skill"] / ["mcp:get_weather"] / ["knowledge_base:exams"] / []
    }}
  ]
}}

用户请求：{query}
"""


# ==================== 意图分类常量 ====================

# 可直接构建子任务的意图类别（不需要 LLM 分解）
EXECUTABLE_CATEGORIES = {"mcp", "skill", "rag", "chat", "system"}

# 复杂规划意图类别（需要 LLM 分解为子任务）
COMPLEX_PLAN_CATEGORY = "complex_plan"


# ==================== Planner 分解节点 ====================

class PlannerDecomposeNode:
    """
    Planner 分解节点（统一路由入口）

    所有意图统一进入此节点，Planner 内部区分处理：
      1. 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务，不调 LLM
      2. complex_plan 意图 → 逐个独立调用 LLM 分解（保留完整规划能力）
      3. 合并为统一的子任务列表

    分解结果写入 state["planned_subtasks"]，由 planner_dispatch 节点按波次调度。
    """

    def __init__(self, ai_client, plugin_registry):
        """
        Args:
            ai_client: AIClient 实例，用于调用 with_structured_output
            plugin_registry: PluginRegistry 实例，用于动态获取能力描述和路由映射
        """
        self._ai_client = ai_client
        self._plugin_registry = plugin_registry

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        分解任务为子任务列表（统一路由入口）

        Args:
            state: 当前状态（包含 query、intents 等）

        Returns:
            更新后的状态（包含 planned_subtasks）
        """
        writer = get_stream_writer()
        query = state["query"]
        intents = state.get("intents", [])

        writer(Step.PLANNER_DECOMPOSE.started_event())
        log(f"[PlannerDecompose] 分解任务: {query[:50]}...", "MultiAgent")

        # 分离意图
        executable_intents, plan_intents = self._separate_intents(intents)

        # 步骤 1：可执行意图直接构建子任务
        subtasks = self._build_subtasks_from_intents(executable_intents)
        self._log_subtasks(subtasks, prefix="可执行意图构建")

        # 步骤 2：每个 complex_plan 意图独立分解后追加
        for plan_intent in plan_intents:
            plan_subtasks = self._decompose_single_plan(plan_intent, existing_count=len(subtasks))
            subtasks.extend(plan_subtasks)

        # 兜底：无任何子任务
        if not subtasks:
            subtasks = self._build_fallback_subtask(query)
            log("[PlannerDecompose] 无子任务，回退到 chat", "MultiAgent")

        writer(Step.PLANNER_DECOMPOSE.completed_event(detail=f"{len(subtasks)} 个子任务"))

        return {
            "planned_subtasks": subtasks,
            "agent_results": None,  # 重置，避免跨请求累积
        }

    # -------------------- 意图分离 --------------------

    @staticmethod
    def _separate_intents(intents: List[Dict[str, Any]]) -> tuple:
        """
        将意图列表分离为可执行意图和复杂规划意图

        Args:
            intents: 原始意图列表

        Returns:
            (executable_intents, plan_intents) 元组
        """
        executable_intents = []
        plan_intents = []

        for intent in intents:
            category = intent.get("category", "")
            if category in EXECUTABLE_CATEGORIES:
                executable_intents.append(intent)
            elif category == COMPLEX_PLAN_CATEGORY:
                plan_intents.append(intent)
            else:
                executable_intents.append(intent)

        return executable_intents, plan_intents

    # -------------------- 可执行意图构建子任务 --------------------

    @staticmethod
    def _build_subtasks_from_intents(intents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从可执行意图直接构建子任务列表

        同一类别的多个意图合并为一个子任务（该 Expert 内部会串行处理）。

        Args:
            intents: 可执行意图列表

        Returns:
            子任务列表
        """
        category_data = _group_intents_by_category(intents)

        subtasks = []
        for cat, data in category_data.items():
            subtask_category = "chat" if cat in ("chat", "system") else cat
            subtasks.append({
                "description": "；".join(data["contents"]),
                "category": subtask_category,
                "depends_on": [],
                "targets": data["targets"],
            })
        return subtasks

    # -------------------- 单个 complex_plan 意图独立分解 --------------------

    def _decompose_single_plan(self, plan_intent: Dict[str, Any], existing_count: int) -> List[Dict[str, Any]]:
        """
        用 LLM 独立分解单个 complex_plan 意图

        Args:
            plan_intent: 单个 complex_plan 意图
            existing_count: 已有子任务数量（用于偏移 depends_on 索引）

        Returns:
            分解后的子任务列表（depends_on 已偏移）
        """
        content = plan_intent.get("content", "")
        if not content:
            return []

        log(f"[PlannerDecompose] 独立分解 complex_plan: {content[:40]}...", "MultiAgent")

        decomposition = self._invoke_decomposition_llm(content)
        if decomposition is None:
            log(f"[PlannerDecompose] complex_plan 分解失败，回退为 chat 子任务: {content[:30]}...", "MultiAgent")
            return [{
                "description": content,
                "category": "chat",
                "depends_on": [],
            }]

        subtasks = self._convert_decomposition(decomposition, existing_count)
        self._log_subtasks(subtasks, prefix=f"complex_plan 分解({decomposition.reasoning[:30]}...)")

        return subtasks

    def _invoke_decomposition_llm(self, query: str) -> Optional[TaskDecomposition]:
        """
        调用 LLM 进行任务分解

        Args:
            query: 待分解的用户请求

        Returns:
            TaskDecomposition 实例，失败返回 None
        """
        capability_descriptions = self._plugin_registry.build_capability_descriptions()
        prompt = DECOMPOSE_PROMPT.format(
            query=query,
            capability_descriptions=capability_descriptions,
        )

        try:
            structured_llm = self._ai_client.chat.with_structured_output(
                TaskDecomposition, method="json_mode"
            )
            return structured_llm.invoke(prompt)
        except Exception as e:
            log(f"[PlannerDecompose] LLM 分解调用失败: {e}", "MultiAgent")
            return None

    @staticmethod
    def _convert_decomposition(decomposition: TaskDecomposition, existing_count: int) -> List[Dict[str, Any]]:
        """
        将 TaskDecomposition 转换为子任务字典列表，并偏移 depends_on 索引

        Args:
            decomposition: LLM 返回的分解结果
            existing_count: 已有子任务数量

        Returns:
            子任务字典列表（depends_on 已偏移为全局索引）
        """
        subtasks = []
        for sub in decomposition.subtasks:
            sub_dict = sub.model_dump()
            sub_dict["depends_on"] = [d + existing_count for d in sub_dict.get("depends_on", [])]
            subtasks.append(sub_dict)
        return subtasks

    # -------------------- 兜底 --------------------

    @staticmethod
    def _build_fallback_subtask(query: str) -> List[Dict[str, Any]]:
        """
        构建兜底子任务（当所有分解均失败时）

        Args:
            query: 用户原始请求

        Returns:
            包含单个 chat 子任务的列表
        """
        return [{
            "description": query,
            "category": "chat",
            "depends_on": [],
        }]

    # -------------------- 日志 --------------------

    @staticmethod
    def _log_subtasks(subtasks: List[Dict[str, Any]], prefix: str = ""):
        """
        记录子任务列表日志

        Args:
            subtasks: 子任务列表
            prefix: 日志前缀描述
        """
        log(f"[PlannerDecompose] {prefix} {len(subtasks)} 个子任务", "MultiAgent")
        for i, sub in enumerate(subtasks):
            deps = sub.get("depends_on", [])
            log(
                f"[PlannerDecompose]   子任务[{i}]: category={sub['category']}, "
                f"depends_on={deps}, desc={sub['description'][:40]}...",
                "MultiAgent",
            )


# ==================== 辅助函数 ====================

def _group_intents_by_category(intents: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    按类别分组可执行意图

    同一类别的意图合并为一条记录，保留 contents 和 targets 列表。
    chat 和 system 意图合并到同一组（统一由 chat_expert 处理）。

    Args:
        intents: 可执行意图列表

    Returns:
        {category: {"contents": [...], "targets": [...]}}
    """
    category_data: Dict[str, Dict[str, Any]] = {}
    for intent in intents:
        cat = intent.get("category", "")
        group_key = "chat" if cat in ("chat", "system") else cat
        if group_key not in EXECUTABLE_CATEGORIES:
            continue
        content = intent.get("content", "")
        target = intent.get("target", "")
        if group_key not in category_data:
            category_data[group_key] = {"contents": [], "targets": []}
        category_data[group_key]["contents"].append(content)
        category_data[group_key]["targets"].append(target)
    return category_data


def create_planner_decompose(ai_client, plugin_registry):
    """
    创建 Planner 分解节点

    Args:
        ai_client: AIClient 实例
        plugin_registry: PluginRegistry 实例

    Returns:
        PlannerDecomposeNode 实例
    """
    return PlannerDecomposeNode(ai_client, plugin_registry)
