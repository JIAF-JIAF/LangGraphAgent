"""
Planner 调度节点（波次执行）

检查 planned_subtasks 中哪些子任务的依赖已满足，
将就绪的子任务通过 Send API 并行分发到对应 Expert。
"""

from typing import Dict, Any, List, Optional

from langgraph.config import get_stream_writer
from langgraph.types import Send
from modules.logger import log
from modules.langgraph.nodes.steps import Step


class PlannerDispatchNode:
    """
    Planner 调度节点（波次执行）

    检查 planned_subtasks 中哪些子任务的依赖已满足，
    将就绪的子任务通过 Send API 并行分发到对应 Expert。

    每次调用返回本轮就绪子任务的 Send 列表。
    如果所有子任务已完成，返回 {"__dispatch_complete__": True} 信号。
    """

    def __init__(self, plugin_registry):
        """
        Args:
            plugin_registry: PluginRegistry 实例，用于动态获取路由映射
        """
        self._plugin_registry = plugin_registry

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        调度入口

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

        # 构建分发详情：显示分发给哪个 Expert
        category_map = self._plugin_registry.build_category_map()
        dispatch_desc = "、".join(
            f"子任务{idx}→{category_map.get(subtasks[idx].get('category', ''), '?')}"
            for idx in ready_indices
        )
        log(f"[PlannerDispatch] 本轮就绪子任务: {ready_indices}，已完成: {completed_indices}", "MultiAgent")
        writer(Step.PLANNER_DISPATCH.completed_event(detail=f"分发：{dispatch_desc}"))

        return {"__ready_indices__": ready_indices}

    def build_sends(self, state: Dict[str, Any]) -> list:
        """
        根据就绪子任务索引，构建 Send 列表

        由 graph.py 的条件边调用。

        Args:
            state: 当前状态（包含 planned_subtasks、agent_results、__ready_indices__ 等）

        Returns:
            Send 对象列表，每个 Send 指向一个 Expert 节点
        """
        subtasks = state.get("planned_subtasks", [])
        ready_indices = state.get("__ready_indices__", [])

        if not ready_indices:
            return []

        completed_results = _collect_completed_results(state.get("agent_results", []))

        sends = []
        for idx in ready_indices:
            sub = subtasks[idx]
            send = self._build_single_send(sub, idx, state, completed_results)
            if send:
                sends.append(send)

        return sends

    def _build_single_send(self, subtask, idx, state, completed_results):
        """
        为单个子任务构建 Send 对象

        Args:
            subtask: 子任务字典
            idx: 子任务全局索引
            state: 当前全局状态
            completed_results: 已完成子任务的回答映射

        Returns:
            Send 对象，Expert 不可用时返回 None
        """
        category = subtask.get("category", "")
        if not category:
            category = self._plugin_registry.get_default_fallback_category()
        
        category_map = self._plugin_registry.build_category_map()
        expert_name = category_map.get(category)

        if not expert_name:
            log(f"[PlannerDispatch] 子任务[{idx}] 跳过: 无匹配 Expert（category={category}）", "MultiAgent")
            return None

        expert_state = _build_expert_state(
            subtask, 
            idx, 
            state, 
            completed_results, 
            self._plugin_registry
        )

        log(f"[PlannerDispatch] 子任务[{idx}] → {expert_name}: {expert_state['intents'][0]['content'][:40]}...", "MultiAgent")
        return Send(expert_name, expert_state)


# ==================== 工具函数 ====================


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


def _build_expert_state(subtask: Dict[str, Any], idx: int, state: Dict[str, Any], completed_results: Dict[int, str], plugin_registry) -> Dict[str, Any]:
    """
    构建 Expert 专属 state

    基于全局 state 快照，覆盖意图列表、重置结果、标记子任务索引。

    Args:
        subtask: 子任务字典
        idx: 子任务全局索引
        state: 当前全局状态
        completed_results: 已完成子任务的回答映射
        plugin_registry: PluginRegistry 实例

    Returns:
        Expert 专属 state 字典
    """
    category = subtask.get("category", "")
    if not category:
        category = plugin_registry.get_default_fallback_category()
    description = subtask["description"]

    expert_intents = _restore_intents_from_subtask(subtask, category, plugin_registry)

    deps = subtask.get("depends_on", [])
    if deps:
        description = _inject_dependency_context(description, deps, completed_results)
        expert_intents[0]["content"] = description

    expert_state = dict(state)
    expert_state["intents"] = expert_intents
    expert_state["agent_results"] = []
    expert_state["__subtask_idx__"] = idx

    return expert_state


def _restore_intents_from_subtask(subtask: Dict[str, Any], category: str, plugin_registry) -> List[Dict[str, Any]]:
    """
    从子任务恢复意图列表

    统一使用 targets 列表恢复意图：
      - 有 targets：逐个恢复（可执行意图 或 LLM 正确输出）
      - 无 targets：兜底用 category 前缀，Expert 会走自动匹配

    Args:
        subtask: 子任务字典
        category: 子任务类别
        plugin_registry: PluginRegistry 实例，用于获取 target_prefix

    Returns:
        意图列表
    """
    targets = subtask.get("targets", [])

    # 从 Manifest 获取 target_prefix
    category_map = plugin_registry.build_category_map()
    expert_name = category_map.get(category)
    target_prefix = ""
    if expert_name:
        plugin = plugin_registry.get_plugin(expert_name)
        if plugin:
            target_prefix = plugin.manifest.routing.target_prefix

    if targets:
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
        return [{
            "category": category,
            "target": f"{target_prefix}" if target_prefix else f"{category}:",
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
