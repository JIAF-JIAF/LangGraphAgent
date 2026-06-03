"""
Planner Expert 节点

处理任务规划意图。使用领域专精 Agent（只绑定 Planner 工具），
LLM-in-the-loop 自动完成任务分解和子任务执行。

核心设计：
  - LLM-in-the-loop：任务分解策略由 LLM 决定
  - 工具隔离：Agent 只看到 Planner 工具（含委托工具），从根源杜绝工具幻觉
  - 委托工具：Planner 通过 delegate_to_* 工具调用其他 Expert Agent
  - 意图即上下文：将意图信息作为 Agent 输入提示
  - 无 fallback：规划失败则明确报告，不回退到其他路径
  - 结果写入 agent_results：由 Merge 节点统一润色，不直接写 answer

Planner 执行流程：
  1. decompose_task → 分解复杂任务为子任务
  2. delegate_to_mcp/skill/rag_expert → 委托对应专家执行子任务
  3. summarize_results → 汇总结果
"""

from typing import Dict, Any, List
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.context import AgentContext
from modules.langgraph.nodes.steps import Step


class PlannerExpertNode:
    """
    Planner Expert 节点

    调用领域专精 Agent 执行任务规划和子任务执行。
    Agent 内部通过 ReAct 循环完成任务分解、委托执行和结果汇总。

    _build_input 逻辑与其他 Expert 不同：Planner 保留完整查询（需要全局视角来规划任务）。
    """

    def __init__(self, agent):
        """
        Args:
            agent: Planner 领域专精 Agent 实例（只绑定 Planner 工具，含委托工具）
        """
        self._agent = agent

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务规划和子任务执行

        Args:
            state: 当前状态（包含 query、intents、session_id 等）

        Returns:
            更新后的状态（包含 agent_results）
        """
        writer = get_stream_writer()
        query = state["query"]
        intents = state.get("intents", [])
        planner_intents = [i for i in intents if i.get("category") == "plan"]

        input_text = self._build_input(query, planner_intents)

        writer(Step.PLANNER_EXPERT.started_event())
        log(f"[PlannerExpert] 处理 Planner 意图: {len(planner_intents)} 个, 输入: {input_text[:50]}...", "MultiAgent")

        agent_context = AgentContext(
            session_id=state.get("session_id", "default"),
            chat_history=state.get("chat_history", []),
            feeling=state.get("feeling", {}),
        )

        result = self._agent.invoke(input_text, agent_context)
        answer = result.get("answer", "")

        intent_results = [
            {
                "type": "planner",
                "target": intent.get("target", ""),
                "content": answer,
                "success": True,
            }
            for intent in planner_intents
        ]

        writer(Step.PLANNER_EXPERT.completed_event())
        log(f"[PlannerExpert] 完成: {answer[:50]}...", "MultiAgent")

        return {
            "agent_results": [{"agent": "planner_expert", "answer": answer, "intent_results": intent_results}],
        }

    def _build_input(self, query: str, planner_intents: List[Dict[str, Any]]) -> str:
        """
        构建 Agent 输入（覆写基类）

        Planner 保留完整查询，附加任务描述作为上下文提示。
        与其他 Expert 不同：Planner 需要全局视角来规划任务。

        Args:
            query: 用户原始查询
            planner_intents: plan 类别的意图列表

        Returns:
            构建后的 Agent 输入文本
        """
        if not planner_intents:
            return query

        # Planner 始终保留完整 query，因为规划任务需要全局视角
        parts = [f"用户请求：{query}"]

        if len(planner_intents) == 1:
            parts.extend(self._build_single_planner_input(query, planner_intents[0]))
        else:
            parts.extend(self._build_multi_planner_input(planner_intents))

        return "\n".join(parts)

    def _build_single_planner_input(self, query: str, intent: Dict[str, Any]) -> List[str]:
        """
        构建单规划意图输入：附加任务描述作为上下文

        忽略 target，Planner 不关心具体工具/知识库，只关心任务内容。
        示例输出：
            ["用户请求：帮我查天气并画图", "\n任务描述：规划多步骤任务"]

        Args:
            query: 用户原始查询
            intent: 单个 plan 意图对象

        Returns:
            追加到 parts 的字符串列表
        """
        content = intent.get("content", "")
        if content and content != query:
            return [f"\n任务描述：{content}"]
        return []

    def _build_multi_planner_input(self, planner_intents: List[Dict[str, Any]]) -> List[str]:
        """
        构建多规划意图输入：列出所有规划任务，让 Planner 统筹安排

        示例输出：
            ["\n提示：用户请求涉及多个规划任务", "  1. 规划天气查询和推荐", "  2. 规划技能执行"]

        Args:
            planner_intents: plan 意图列表

        Returns:
            追加到 parts 的字符串列表
        """
        parts = ["\n提示：用户请求涉及多个规划任务"]
        for i, intent in enumerate(planner_intents, 1):
            content = intent.get("content", "")
            parts.append(f"  {i}. {content}")
        return parts


def create_planner_expert(agent):
    """
    创建 Planner Expert 节点函数

    Args:
        agent: Planner 领域专精 Agent 实例

    Returns:
        PlannerExpertNode 实例（可直接 add_node 到主图）
    """
    return PlannerExpertNode(agent)
