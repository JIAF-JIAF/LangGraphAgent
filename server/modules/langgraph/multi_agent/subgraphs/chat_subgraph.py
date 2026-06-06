"""
Chat Expert 节点

处理简单闲聊、问候、简单问答等对话意图。
直接调用 Agent + RefinerRegistry 生成回答。

职责边界（新架构）：
  - chat：简单闲聊、问候、感谢、简单问答（LLM 直接回答即可）
  - complex_plan：需要多步骤规划的需求（如创建应用、设计方案）→ 走 Planner 分解

  chat_expert 不承担复杂规划功能，所有需要规划的需求由 Planner 分解后，
  分解出的 chat 子任务才由 chat_expert 执行。

设计说明：
  - 使用 RefinerRegistry 润色流程，保证回答质量不降
  - 结果写入 agent_results：由 Merge 节点统一处理
  - chat_history 有 add_messages_with_truncation reducer，并行写入安全
  - chat 类别意图注入无工具提示，避免冗余工具调用

注意：不使用编译后的 Subgraph，直接使用节点函数。
  编译后的 Subgraph 会将 MultiAgentState 的所有字段映射回主图 state，
  导致并行执行时 query 等无 reducer 字段冲突。
"""

from typing import Dict, Any, List
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.langgraph.nodes.steps import Step
from modules.langgraph.context_builder import ContextBuilder
from modules.langgraph.refiners import RefineContext, RefinerRegistry


class ChatExpertNode:
    """
    Chat Expert 节点

    仅处理简单闲聊意图（chat 类别），不承担复杂规划功能。
    复杂规划需求（complex_plan）由 Planner 分解后，分解出的 chat 子任务才由本节点执行。

    执行流程：
      1. 检测意图类别是否为 chat
      2. 如果是 chat 类别，注入无工具提示（避免冗余工具调用）
      3. 通过 RefinerRegistry.refine() 选择合适的润色器
      4. 调用 agent 生成回答
      5. 构建 chat_history 增量
    """

    def _generate_subtask_content(self, query: str, state: Dict[str, Any]) -> str:
        """
        为 Planner 子任务生成纯内容（不润色）

        Planner 分解的子任务只需生成内容，润色和整合由 MergeNode 统一处理。
        直接调用 Agent 生成回答，跳过 RefinerRegistry 润色流程。

        Args:
            query: 子任务描述（来自 Planner 分解）
            state: 当前状态

        Returns:
            子任务的纯内容回答
        """
        try:
            chat_history = state.get("chat_history", [])
            response = self._agent.invoke({
                "input": query,
                "chat_history": chat_history,
            })
            if isinstance(response, dict):
                return response.get("output", str(response))
            return str(response)
        except Exception as e:
            log(f"[ChatExpert] 子任务内容生成失败: {e}", "MultiAgent")
            return f"处理失败：{query[:30]}..."

    def __init__(self, agent, refiners):
        """
        Args:
            agent: LangChain Agent 实例
            refiners: 润色器实例列表
        """
        self._agent = agent
        self._refiners = refiners

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行对话处理

        当意图类别为 chat 时（Planner 已确认无匹配的工具/技能/知识库），
        注入提示告知 Agent 不要调用工具，直接对话回答。

        Args:
            state: 当前状态（包含 query、chat_history、feeling 等）

        Returns:
            更新后的状态（包含 agent_results 和 chat_history）
        """
        writer = get_stream_writer()
        query = state["query"]
        intents = state.get("intents", [])

        writer(Step.CHAT_EXPERT.started_event())

        # 判断是否为 Planner 调度的子任务
        is_planner_subtask = state.get("__subtask_idx__") is not None

        # 优先使用 intent content 作为实际查询
        # Planner 调度时，intent content 是子任务描述（如"分析核心功能需求..."）
        # Supervisor 调度时，intent content 是用户原始请求
        if intents:
            actual_query = intents[0].get("content", query)
        else:
            actual_query = query

        log(f"[ChatExpert] 处理对话: {actual_query[:30]}...", "MultiAgent")

        # 如果意图类别为 chat（Planner 已确认无匹配能力），
        # 注入提示让 Agent 跳过工具调用，直接对话
        is_chat_intent = any(
            i.get("category") == "chat" for i in intents
        )
        if is_chat_intent:
            original_query = actual_query
            query = (
                f"[重要提示：此请求已确认无匹配的工具、技能或知识库，请直接通过对话回答，不要调用任何工具。]\n\n"
                f"用户请求：{original_query}"
            )
            log(f"[ChatExpert] chat 类别意图，注入无工具提示", "MultiAgent")
        else:
            query = actual_query

        if is_planner_subtask:
            # Planner 子任务：只生成纯内容，不润色（润色交给 MergeNode 统一处理）
            answer = self._generate_subtask_content(query, state)
            log(f"[ChatExpert] 子任务内容生成完成: {answer[:50]}...", "MultiAgent")
        else:
            # Supervisor 直接调度：走完整润色流程
            context = RefineContext.from_state(state)
            context.query = query
            answer = RefinerRegistry.refine(context, self._agent, self._refiners)

        writer(Step.CHAT_EXPERT.completed_event())
        log(f"[ChatExpert] 完成: {answer[:50]}...", "MultiAgent")

        result = {"agent": "chat_expert", "answer": answer}
        # 如果是 Planner 调度的，携带 subtask_idx 标记
        subtask_idx = state.get("__subtask_idx__")
        if subtask_idx is not None:
            result["subtask_idx"] = subtask_idx

        update = {
            "agent_results": [result],
            "chat_history": ContextBuilder.build_chat_history(query, answer),
        }
        # 回传 __subtask_idx__，确保 _route_expert_after_execution 能正确判断路由
        if subtask_idx is not None:
            update["__subtask_idx__"] = subtask_idx

        return update


def create_chat_expert(agent, refiners: List):
    """
    创建 Chat Expert 节点函数

    Args:
        agent: LangChain Agent 实例
        refiners: 润色器实例列表

    Returns:
        Chat Expert 节点函数（可直接 add_node 到主图）
    """
    return ChatExpertNode(agent, refiners)
