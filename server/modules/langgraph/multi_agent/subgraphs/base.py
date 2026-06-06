"""
Expert 基类

仅提供 _build_input 公共逻辑，子类继承后保持各自的 __call__ 等实现。
"""

from typing import Dict, Any, List


class BaseExpertNode:
    """
    Expert 节点基类

    仅提供 _build_input 公共逻辑。
    子类需设置 target_prefix / single_hint / multi_hint，可覆写 _build_input。
    """

    target_prefix: str = ""
    single_hint: str = ""
    multi_hint: str = ""

    def _get_subtask_idx(self, state: Dict[str, Any]):
        """
        获取 Planner 调度标记的子任务索引

        当 Expert 由 Planner 通过 Send API 调度时，state 中会携带 __subtask_idx__。
        此索引用于 planner_dispatch 节点追踪子任务完成状态。

        Args:
            state: 当前状态

        Returns:
            子任务索引（int）或 None（非 Planner 调度）
        """
        return state.get("__subtask_idx__")

    def _build_result(self, state: Dict[str, Any], agent: str, answer: str,
                      intent_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建 Expert 节点的标准返回结果

        统一处理 agent_results 和 Planner 调度标记（__subtask_idx__），
        所有 Expert 子类共用此方法，避免重复逻辑。

        Args:
            state: 当前状态（用于获取子任务索引）
            agent: Expert 名称（如 "mcp_expert"）
            answer: Agent 生成的回答
            intent_results: 意图执行结果列表

        Returns:
            标准化的状态更新字典
        """
        # 1. 构建 agent_results 条目（Expert 执行结果）
        result_entry = {
            "agent": agent,
            "answer": answer,
            "intent_results": intent_results,
        }

        # 2. 构建状态更新字典（将写入 LangGraph State）
        result = {}

        # 3. 获取 Planner 调度标记：非 None 表示由 Planner 波次调度，None 表示由 Supervisor 直接调度
        subtask_idx = self._get_subtask_idx(state)
        if subtask_idx is not None:
            # 标记1：写入 agent_results 条目，供 MergeNode 按子任务顺序排列结果
            result_entry["subtask_idx"] = subtask_idx

        # 4. 将结果条目写入 agent_results（通过 add_agent_results reducer 追加到 State）
        result["agent_results"] = [result_entry]

        # 5. 回传调度标记到 State 顶层
        if subtask_idx is not None:
            # 标记2：供 _route_expert_after_execution 判断路由方向
            #   - 有 __subtask_idx__ → Planner 调度 → 回到 planner_dispatch 继续波次调度
            #   - 无 __subtask_idx__ → Supervisor 调度 → 直接去 merge 汇总
            result["__subtask_idx__"] = subtask_idx

        return result

    def _build_input(self, query: str, intents: List[Dict[str, Any]]) -> str:
        """
        构建 Agent 输入

        只使用当前 Expert 相关类别的意图内容，避免其他类别意图污染。
        子类可覆写此方法实现自定义逻辑（如 Planner）。

        Args:
            query: 用户原始查询
            intents: 当前 Expert 相关类别的意图列表

        Returns:
            构建后的 Agent 输入文本
        """
        if not intents:
            return query

        if len(intents) == 1:
            return self._build_single_intent_input(query, intents[0])

        return self._build_multi_intent_input(query, intents)

    def _build_single_intent_input(self, query: str, intent: Dict[str, Any]) -> str:
        """
        构建单意图输入：用 hint 引导 Agent 聚焦到具体目标

        示例输出（RAG Expert）：
            "请在 exams 知识库中检索以下内容\n行测蒙题技巧"

        Args:
            query: 用户原始查询
            intent: 单个意图对象

        Returns:
            构建后的 Agent 输入文本
        """
        parts = []
        target = intent.get("target", "").replace(self.target_prefix, "")
        content = intent.get("content", "")

        if target:
            parts.append(self.single_hint.format(target=target))
        parts.append(content if content else query)

        return "\n".join(parts)

    def _build_multi_intent_input(self, query: str, intents: List[Dict[str, Any]]) -> str:
        """
        构建多意图输入：列出所有意图，让 Agent 依次处理

        示例输出（MCP Expert）：
            "请完成以下工具调用任务：
              1. [weather] 查询杭州天气
              2. [weather_recommend] 推荐游玩地点"

        Args:
            query: 用户原始查询
            intents: 意图列表

        Returns:
            构建后的 Agent 输入文本
        """
        parts = [self.multi_hint]
        for i, intent in enumerate(intents, 1):
            target = intent.get("target", "").replace(self.target_prefix, "")
            content = intent.get("content", "")

            if target:
                parts.append(f"  {i}. [{target}] {content}")
            else:
                parts.append(f"  {i}. {content}")

        return "\n".join(parts)
