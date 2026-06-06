"""
MCP Expert 节点

处理 MCP 工具调用意图。使用领域专精 Agent（只绑定 MCP 工具），
LLM-in-the-loop 自动完成参数提取和工具选择。

核心设计：
  - LLM-in-the-loop：参数提取由 LLM 完成，不手动拼装
  - 工具隔离：Agent 只看到 MCP 工具，从根源杜绝工具幻觉
  - 意图即上下文：将意图信息作为 Agent 输入的上下文提示
  - 无 fallback：失败则明确报告，不回退到其他路径
  - 结果写入 agent_results：由 Merge 节点统一润色，不直接写 answer

多 MCP 执行：
  - Agent 的 ReAct 循环天然支持顺序多工具调用
  - 前一个工具的返回值可作为后一个工具的输入
  - 例如：先查天气 → 再根据天气推荐活动
"""

from typing import Dict, Any, List
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.context import AgentContext
from modules.langgraph.nodes.steps import Step
from modules.langgraph.multi_agent.subgraphs.base import BaseExpertNode


class MCPExpertNode(BaseExpertNode):
    """
    MCP Expert 节点

    调用领域专精 Agent 执行 MCP 工具调用。
    Agent 内部通过 ReAct 循环完成：
      1. LLM 选择工具 + 提取参数
      2. 执行工具调用
      3. 将结果反馈给 LLM
      4. LLM 决定是否继续调用或生成最终回答
    """

    target_prefix = "mcp:"
    single_hint = "请使用 {target} 工具完成以下任务"
    multi_hint = "请完成以下工具调用任务："

    def __init__(self, agent):
        """
        Args:
            agent: MCP 领域专精 Agent 实例（只绑定 MCP 工具）
        """
        self._agent = agent

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 MCP 工具调用

        Args:
            state: 当前状态（包含 query、intents、session_id 等）

        Returns:
            更新后的状态（包含 agent_results）
        """
        writer = get_stream_writer()
        query = state["query"]
        intents = state.get("intents", [])
        mcp_intents = [i for i in intents if i.get("category") == "mcp"]

        input_text = self._build_input(query, mcp_intents)

        writer(Step.MCP_EXPERT.started_event())
        log(f"[MCPExpert] 处理 MCP 意图: {len(mcp_intents)} 个, 输入: {input_text[:50]}...", "MultiAgent")

        agent_context = AgentContext(
            session_id=state.get("session_id", "default"),
            chat_history=state.get("chat_history", []),
            feeling=state.get("feeling", {}),
        )

        result = self._agent.invoke(input_text, agent_context)
        answer = result.get("answer", "")

        intent_results = [
            {
                "type": "mcp",
                "target": intent.get("target", ""),
                "content": answer,
                "success": True,
            }
            for intent in mcp_intents
        ]

        writer(Step.MCP_EXPERT.completed_event())
        log(f"[MCPExpert] 完成: {answer[:50]}...", "MultiAgent")

        return self._build_result(
            state, 
            "mcp_expert", 
            answer, 
            intent_results
        )


def create_mcp_expert(agent):
    """
    创建 MCP Expert 节点函数

    Args:
        agent: MCP 领域专精 Agent 实例

    Returns:
        MCPExpertNode 实例（可直接 add_node 到主图）
    """
    return MCPExpertNode(agent)
