"""
Planner 分解节点（Orchestrator-Worker 模式）

将复杂任务分解为可并行的子任务列表，由图编排层（Send API）调度执行。

核心设计：
  - 结构化输出：使用 llm.with_structured_output(TaskDecomposition) 强制约束输出格式
  - 依赖感知：子任务可声明 depends_on，支持跨 Expert 串行依赖
  - 图编排层并行：独立子任务由 Send API 并行分发，依赖子任务按波次执行
  - 独立分解：每个 complex_plan 意图独立调用 LLM 分解，保证分解质量不受上下文干扰

执行流程：
  planner_decompose → planner_dispatch ──→ Send(expert) ──→ planner_dispatch (循环)
                                            ↓ (全部完成)
                                          merge → END

对照旧架构（Planner ReAct Agent + delegate_to_* 工具）：
  - 旧：decompose_task → delegate_to_mcp → delegate_to_rag → summarize_results（串行）
  - 新：decompose → dispatch(Send) → Expert 并行 → merge（并行 + 波次依赖）
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langgraph.config import get_stream_writer
from langgraph.types import Send
from modules.logger import log
from modules.langgraph.nodes.steps import Step
from modules.intent.intent_types import IntentCategory


# ==================== Pydantic 结构化输出模型 ====================

class PlannedSubtask(BaseModel):
    """
    单个规划子任务

    Attributes:
        description: 子任务描述，包含足够信息让 Expert 独立执行
        category: 目标 Expert 类别（mcp / skill / rag / chat）
        depends_on: 依赖的子任务索引列表（0-based），空列表表示可立即执行
        target: 目标标识，格式为 "类别前缀:具体ID"，如 "skill:drawio-skill"、"mcp:get_weather"；
                chat 类别留空。用于 Expert 精准路由，避免用描述文字拼凑导致路由失败
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
- mcp: 外部工具调用。当前可用工具：{mcp_tools}
- skill: 技能执行。当前可用技能：{skills}
- rag: 知识库检索。当前可用知识库：{knowledge_bases}
- chat: 对话处理（仅用于简单问答、闲聊等 LLM 可直接回答的任务）

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

# 可执行意图类别（直接构建子任务，无需 LLM 分解）
EXECUTABLE_CATEGORIES = {"mcp", "skill", "rag"}

# 复杂规划意图类别（需要 LLM 分解为子任务）
COMPLEX_PLAN_CATEGORY = "complex_plan"


# ==================== Planner 分解节点 ====================

class PlannerDecomposeNode:
    """
    Planner 分解节点

    混合策略：
      1. 可执行意图（mcp/skill/rag）直接构建子任务
      2. complex_plan 意图逐个独立调用 LLM 分解（方案A：每个目标独立分解）
      3. 合并为统一的子任务列表

    方案A 的核心优势：
      - 每个 complex_plan 意图独立分解，LLM 注意力 100% 聚焦单个目标
      - 分解质量不受其他意图上下文干扰，保证一致性
      - 与 Plandex Plan Tree 理念一致：每个目标是独立的 Plan 节点

    分解结果写入 state["planned_subtasks"]，由 planner_dispatch 节点按波次调度。
    """

    def __init__(self, ai_client, intent_registry=None):
        """
        Args:
            ai_client: AIClient 实例，用于调用 with_structured_output
            intent_registry: IntentRegistry 实例，用于获取可用能力清单（可选）
        """
        self._ai_client = ai_client
        self._intent_registry = intent_registry

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        分解复杂任务为子任务列表

        混合策略：
          1. 可执行意图（mcp/skill/rag）直接构建子任务
          2. complex_plan 意图逐个独立分解后追加
          3. 合并为统一的子任务列表

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

        return executable_intents, plan_intents

    # -------------------- 可执行意图构建子任务 --------------------

    @staticmethod
    def _build_subtasks_from_intents(intents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从可执行意图直接构建子任务列表

        同一类别的多个意图合并为一个子任务（该 Expert 内部会串行处理）。

        Args:
            intents: 可执行意图列表（category 为 mcp/skill/rag）

        Returns:
            子任务列表
        """
        category_data = _group_intents_by_category(intents)

        subtasks = []
        for cat, data in category_data.items():
            subtasks.append({
                "description": "；".join(data["contents"]),
                "category": cat,
                "depends_on": [],
                "targets": data["targets"],
            })
        return subtasks

    # -------------------- 单个 complex_plan 意图独立分解 --------------------

    def _decompose_single_plan(self, plan_intent: Dict[str, Any], existing_count: int) -> List[Dict[str, Any]]:
        """
        用 LLM 独立分解单个 complex_plan 意图

        方案A 核心：每个 complex_plan 意图单独调用一次 LLM，
        保证 LLM 注意力 100% 聚焦该目标，分解质量不受其他意图干扰。

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

        # 调用 LLM 分解
        decomposition = self._invoke_decomposition_llm(content)
        if decomposition is None:
            log(f"[PlannerDecompose] complex_plan 分解失败，回退为 chat 子任务: {content[:30]}...", "MultiAgent")
            return [{
                "description": content,
                "category": "chat",
                "depends_on": [],
            }]

        # 转换并偏移索引
        subtasks = self._convert_decomposition(decomposition, existing_count)

        self._log_subtasks(subtasks, prefix=f"complex_plan 分解({decomposition.reasoning[:30]}...)")

        return subtasks

    def _invoke_decomposition_llm(self, query: str) -> Optional[TaskDecomposition]:
        """
        调用 LLM 进行任务分解

        使用 json_mode 而非默认的 function_calling。
        原因：DashScope API 对 function calling 的 schema 约束力不足，
        LLM 可能不按 TaskDecomposition 的结构返回（如直接返回子任务数组）。
        json_mode 使用 response_format: json_object，DashScope 原生支持，
        配合 Prompt 中的格式描述引导 LLM 输出正确的 JSON 结构。

        Args:
            query: 待分解的用户请求

        Returns:
            TaskDecomposition 实例，失败返回 None
        """
        capabilities = self._get_capability_summary()
        prompt = DECOMPOSE_PROMPT.format(
            query=query,
            mcp_tools=capabilities["mcp_tools"],
            skills=capabilities["skills"],
            knowledge_bases=capabilities["knowledge_bases"],
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

        LLM 返回的 depends_on 索引从 0 开始（相对于本次分解结果），
        需加上已有子任务数量（existing_count）才能对应全局索引。

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

    # -------------------- 能力摘要 --------------------

    def _get_capability_summary(self) -> Dict[str, str]:
        """
        从意图注册表提取各类别的可用能力摘要

        Returns:
            {"mcp_tools": "...", "skills": "...", "knowledge_bases": "..."}
        """
        if not self._intent_registry:
            return {"mcp_tools": "（未获取）", "skills": "（未获取）", "knowledge_bases": "（未获取）"}

        summaries = {"mcp_tools": [], "skills": [], "knowledge_bases": []}
        all_intents = self._intent_registry.get_all_intents()

        for intent_type, intent_info in all_intents.items():
            category = intent_info.get("category")
            description = intent_info.get("description", "")
            name = (
                intent_info.get("tool_name")
                or intent_info.get("skill_name")
                or intent_info.get("knowledge_base")
                or intent_type
            )

            if category == IntentCategory.MCP:
                summaries["mcp_tools"].append(f"{name}（{description}）")
            elif category == IntentCategory.SKILL:
                summaries["skills"].append(f"{name}（{description}）")
            elif category == IntentCategory.RAG:
                summaries["knowledge_bases"].append(f"{name}（{description}）")

        return {
            "mcp_tools": "、".join(summaries["mcp_tools"]) or "无",
            "skills": "、".join(summaries["skills"]) or "无",
            "knowledge_bases": "、".join(summaries["knowledge_bases"]) or "无",
        }

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

    Args:
        intents: 可执行意图列表（category 为 mcp/skill/rag）

    Returns:
        {category: {"contents": [...], "targets": [...]}}
    """
    category_data: Dict[str, Dict[str, Any]] = {}
    for intent in intents:
        cat = intent.get("category", "")
        if cat not in EXECUTABLE_CATEGORIES:
            continue
        content = intent.get("content", "")
        target = intent.get("target", "")
        if cat not in category_data:
            category_data[cat] = {"contents": [], "targets": []}
        category_data[cat]["contents"].append(content)
        category_data[cat]["targets"].append(target)
    return category_data


def create_planner_decompose(ai_client, intent_registry=None):
    """
    创建 Planner 分解节点

    Args:
        ai_client: AIClient 实例
        intent_registry: IntentRegistry 实例，用于获取可用能力清单（可选）

    Returns:
        PlannerDecomposeNode 实例
    """
    return PlannerDecomposeNode(ai_client, intent_registry=intent_registry)


# ==================== Planner 调度节点 ====================

# 类别 → Expert 节点名映射
CATEGORY_EXPERT_MAP = {
    "mcp": "mcp_expert",
    "skill": "skill_expert",
    "rag": "rag_expert",
    "chat": "chat_expert",
}


def planner_dispatch(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Planner 调度节点（波次执行）

    检查 planned_subtasks 中哪些子任务的依赖已满足，
    将就绪的子任务通过 Send API 并行分发到对应 Expert。

    每次调用返回本轮就绪子任务的 Send 列表。
    如果所有子任务已完成，返回 {"__dispatch_complete__": True} 信号。

    Args:
        state: 当前状态（包含 planned_subtasks、agent_results 等）

    Returns:
        状态更新字典（包含调度信号或空结果）
    """
    writer = get_stream_writer()
    subtasks = state.get("planned_subtasks", [])
    agent_results = state.get("agent_results", [])

    writer(Step.PLANNER_DISPATCH.started_event())

    completed_indices = _collect_completed_indices(agent_results)
    ready_indices = _find_ready_subtasks(subtasks, completed_indices)

    if not ready_indices:
        writer(Step.PLANNER_DISPATCH.completed_event(detail="全部完成"))
        log(f"[PlannerDispatch] 所有子任务已完成（{len(completed_indices)}/{len(subtasks)}）", "MultiAgent")
        return {"__dispatch_complete__": True}

    log(f"[PlannerDispatch] 本轮就绪子任务: {ready_indices}，已完成: {completed_indices}", "MultiAgent")
    writer(Step.PLANNER_DISPATCH.completed_event(detail=f"分发 {len(ready_indices)} 个子任务"))

    return {"__ready_indices__": ready_indices}


def build_planner_sends(state: Dict[str, Any]) -> list:
    """
    根据 planner_dispatch 的就绪子任务索引，构建 Send 列表

    由 graph.py 的 _route_from_planner_dispatch 条件边调用。

    Args:
        state: 当前状态（包含 planned_subtasks、agent_results、__ready_indices__ 等）

    Returns:
        Send 对象列表，每个 Send 指向一个 Expert 节点
    """
    subtasks = state.get("planned_subtasks", [])
    ready_indices = state.get("__ready_indices__", [])

    if not ready_indices:
        return []

    # 收集已完成子任务的结果，用于注入依赖上下文
    completed_results = _collect_completed_results(state.get("agent_results", []))

    sends = []
    for idx in ready_indices:
        sub = subtasks[idx]
        send = _build_single_send(sub, idx, state, completed_results)
        if send:
            sends.append(send)

    return sends


def _collect_completed_indices(agent_results: List[Dict[str, Any]]) -> set:
    """
    从 agent_results 中收集已完成的子任务索引集合

    Args:
        agent_results: 各 Expert 返回的结果列表

    Returns:
        已完成的子任务索引集合
    """
    indices = set()
    for result in agent_results:
        subtask_idx = result.get("subtask_idx")
        if subtask_idx is not None:
            indices.add(subtask_idx)
    return indices


def _find_ready_subtasks(subtasks: List[Dict[str, Any]], completed_indices: set) -> List[int]:
    """
    找出本轮可执行的子任务索引（依赖已全部满足）

    Args:
        subtasks: 子任务列表
        completed_indices: 已完成的子任务索引集合

    Returns:
        就绪子任务的索引列表
    """
    ready = []
    for i, sub in enumerate(subtasks):
        if i in completed_indices:
            continue
        deps = sub.get("depends_on", [])
        if all(d in completed_indices for d in deps):
            ready.append(i)
    return ready


def _collect_completed_results(agent_results: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    从 agent_results 中收集已完成子任务的回答

    Args:
        agent_results: 各 Expert 返回的结果列表

    Returns:
        {子任务索引: 回答文本}
    """
    results = {}
    for result in agent_results:
        idx = result.get("subtask_idx")
        if idx is not None:
            results[idx] = result.get("answer", "")
    return results


def _build_single_send(subtask: Dict[str, Any], idx: int, state: Dict[str, Any], completed_results: Dict[int, str]) -> Optional[Any]:
    """
    为单个子任务构建 Send 对象

    Args:
        subtask: 子任务字典
        idx: 子任务全局索引
        state: 当前全局状态（用于构建 Expert 专属 state）
        completed_results: 已完成子任务的回答映射

    Returns:
        Send 对象，Expert 不可用时返回 None
    """
    category = subtask.get("category", "mcp")
    expert_name = CATEGORY_EXPERT_MAP.get(category)

    if not expert_name:
        log(f"[PlannerDispatch] 子任务[{idx}] 跳过: 无匹配 Expert（category={category}）", "MultiAgent")
        return None

    # 构建 Expert 专属 state
    expert_state = _build_expert_state(subtask, idx, state, completed_results)

    log(f"[PlannerDispatch] 子任务[{idx}] → {expert_name}: {expert_state['intents'][0]['content'][:40]}...", "MultiAgent")
    return Send(expert_name, expert_state)


def _build_expert_state(subtask: Dict[str, Any], idx: int, state: Dict[str, Any], completed_results: Dict[int, str]) -> Dict[str, Any]:
    """
    构建 Expert 专属 state

    基于全局 state 快照，覆盖意图列表、重置结果、标记子任务索引。

    Args:
        subtask: 子任务字典
        idx: 子任务全局索引
        state: 当前全局状态
        completed_results: 已完成子任务的回答映射

    Returns:
        Expert 专属 state 字典
    """
    category = subtask.get("category", "mcp")
    description = subtask["description"]

    # 从子任务的 targets 列表恢复原始意图
    expert_intents = _restore_intents_from_subtask(subtask, category)

    # 注入依赖上下文到子任务描述
    deps = subtask.get("depends_on", [])
    if deps:
        description = _inject_dependency_context(description, deps, completed_results)
        expert_intents[0]["content"] = description

    # 基于 state 快照构建 Expert 专属 state
    expert_state = dict(state)
    expert_state["intents"] = expert_intents
    expert_state["agent_results"] = []
    expert_state["__subtask_idx__"] = idx

    return expert_state


def _restore_intents_from_subtask(subtask: Dict[str, Any], category: str) -> List[Dict[str, Any]]:
    """
    从子任务恢复意图列表

    统一使用 targets 列表恢复意图：
      - 有 targets：逐个恢复（可执行意图 或 LLM 正确输出）
      - 无 targets：兜底用 category 前缀，Expert 会走自动匹配

    Args:
        subtask: 子任务字典
        category: 子任务类别

    Returns:
        意图列表
    """
    targets = subtask.get("targets", [])

    if targets:
        # 有 targets（可执行意图 或 LLM 正确输出）
        contents = subtask["description"].split("；")
        return [
            {
                "category": category,
                "target": target,
                "content": contents[i] if i < len(contents) else subtask["description"],
            }
            for i, target in enumerate(targets)
        ]
    else:
        # 兜底：无 targets，用 category 前缀 + 空后缀，Expert 会走自动匹配
        return [{
            "category": category,
            "target": f"{category}:",
            "content": subtask["description"],
        }]


def _inject_dependency_context(description: str, deps: List[int], completed_results: Dict[int, str]) -> str:
    """
    将依赖子任务的结果注入到描述中

    Args:
        description: 原始子任务描述
        deps: 依赖的子任务索引列表
        completed_results: 已完成子任务的回答映射

    Returns:
        注入依赖上下文后的描述
    """
    dep_context = "\n".join(
        f"[子任务{d}的结果]: {completed_results.get(d, '（无结果）')}"
        for d in deps
    )
    return f"{description}\n\n前置依赖信息：\n{dep_context}"
