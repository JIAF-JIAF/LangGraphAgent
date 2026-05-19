"""
LangGraph Agent 实现

标准 LangGraph RAG 流程，增强版包含任务规划、反思校验和技能匹配：

START → feeling_detect → skill_match → ┌── 匹配到技能 ──→ skill_runner → END
                                       │
                                       └── 未匹配技能 ──→ router → ┌── 需要检索 ──→ retrieve → generate → plan
                                                               │                                        │
                                                               └── 不需要检索 ──→ plan ←─────────────────┘
                                                                                    │
                                                                                    ▼
                                                                  execute_task → reflect → check_task_complete → ┌── 有更多任务 ──→ execute_task
                                                                                │                                     │
                                                                                └─────────────────────────────────────┴── 所有任务完成 ──→ call_model → END

采用 LangGraph 标准会话管理：
- 使用 Checkpointer 进行状态持久化
- 通过 thread_id 实现会话隔离
- 在 call_model 节点中更新对话历史
- 支持感情侦测，动态更新 prompt
- 支持任务规划和反思校验
- 支持技能匹配：命中 skill 后统一走 skill_runner 执行
"""

import time
from typing import Optional, Dict, Any, List, Literal
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState
from .task_generators import TaskGeneratorChain
from modules.prompt import create_prompt


class LangGraphAgent:
    """
    LangGraph Agent（增强版）

    核心功能：
    - 调用 RAGWorkflow 处理检索逻辑（可替换）
    - 调用外部 Agent 处理对话（可替换）
    - 使用 Checkpointer 进行状态持久化（可替换）
    - 支持感情侦测，动态更新 prompt（可替换）
    - 支持任务规划：将复杂需求拆分为子任务（可替换）
    - 支持反思校验：验证回答质量，自动重试（可替换）
    - 支持技能匹配：根据用户查询匹配专业技能（可替换）

    设计理念：
    - 所有核心组件均通过构造函数注入，内部不感知具体实现
    - 通过鸭子类型实现多态，只需实现约定的接口方法即可替换
    - 保持架构灵活性，支持多种实现方案无缝切换
    """

    def __init__(
        self,
        agent: Any,
        rag_workflow: Any,
        checkpointer: Any,
        feeling_detector: Any,
        task_planner: Any,
        reflection_checker: Any,
        skill_manager: Any = None,
        verbose: bool = True,
        max_retries: int = 3
    ):
        """
        初始化 LangGraph Agent

        Args:
            agent: 外部 Agent 实例（可替换），需实现 invoke(query, session_id, chat_history, feeling, uid) 方法
            rag_workflow: RAGWorkflow 实例（可替换），用于处理检索逻辑
            checkpointer: 检查点存储实例（可替换），需实现 LangGraph CheckpointSaver 接口
            feeling_detector: 感情侦测器实例（可替换），需实现 detect(text, detailed) 方法
            task_planner: 任务规划器实例（可替换），需实现 plan(query, context) 方法
            reflection_checker: 反思校验器实例（可替换），需实现 reflect(query, answer, documents) 方法
            skill_manager: 技能管理器实例（可替换），需实现 match_skill(query) 和 generate_skill_prompt(skill, query) 方法
            verbose: 是否输出详细日志
            max_retries: 最大重试次数（默认3次）

        替换说明：
        - 所有标注"(可替换)"的参数均可传入不同实现
        - 内部仅依赖约定接口，不依赖具体实现类
        - 实现方式由调用方决定，内部不感知
        """
        self._agent = agent
        self._rag_workflow = rag_workflow
        self._skill_manager = skill_manager
        self._checkpointer = checkpointer
        self._feeling_detector = feeling_detector
        self._task_planner = task_planner
        self._reflection_checker = reflection_checker
        self._verbose = verbose
        self._max_retries = max_retries
        self._graph = None

        self._build_graph()

    def _log(self, message: str, level: str = "INFO"):
        """
        输出日志

        Args:
            message: 日志消息
            level: 日志级别
        """
        if self._verbose:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [LangGraph] [{level}] {message}", flush=True)

    def _feeling_detect_node(self, state: AgentState) -> AgentState:
        """
        感情侦测节点：分析用户输入的情绪状态

        Args:
            state: 当前状态（包含 query）

        Returns:
            更新后的状态（包含 feeling）
        """
        query = state["query"]
        self._log(f"[节点: feeling_detect] 开始执行，查询: {query[:30]}...")
        
        feeling = self._feeling_detector.detect(query, True)
        self._log(f"[节点: feeling_detect] 情绪分析结果: {feeling}")
        
        return {"feeling": feeling}

    def _skill_match_node(self, state: AgentState) -> AgentState:
        """
        技能匹配节点：根据用户查询匹配专业技能

        Args:
            state: 当前状态（包含 query）

        Returns:
            更新后的状态（包含 matched_skill）
        """
        query = state["query"]
        self._log(f"[节点: skill_match] 开始技能匹配，查询: {query[:30]}...")
        
        matched_skill = self._skill_manager.match_skill(query)
        
        if matched_skill:
            self._log(f"[节点: skill_match] 匹配到技能: {matched_skill['name']} - {matched_skill['title']}")
        else:
            self._log(f"[节点: skill_match] 未匹配到技能，使用默认流程")
        
        return {"matched_skill": matched_skill}

    def _skill_runner_node(self, state: AgentState) -> AgentState:
        """
        技能执行节点：使用 skill_runner 执行命中的技能

        Args:
            state: 当前状态（包含 query, matched_skill）

        Returns:
            更新后的状态（包含执行结果）
        """
        query = state["query"]
        matched_skill = state.get("matched_skill")

        if not matched_skill:
            self._log(f"[节点: skill_runner] 未匹配到技能，跳过")
            return {"answer": "", "skill_executed": False}

        skill_name = matched_skill.get("name", "")
        self._log(f"[节点: skill_runner] 开始执行技能: {skill_name}")

        try:
            result = self._skill_manager.execute_skill(skill_name=skill_name, query=query)

            self._log(f"[节点: skill_runner] 执行完成: success={result.success}, output_len={len(result.final_output)}")

            return {
                "answer": result.final_output or result.error,
                "skill_executed": True,
                "skill_name": skill_name,
                "skill_success": result.success,
                "skill_steps": [
                    {
                        "number": s.step_number,
                        "name": s.step_name,
                        "status": s.status.value,
                        "output": s.output,
                        "duration": s.duration
                    }
                    for s in result.steps
                ]
            }
        except Exception as e:
            self._log(f"[节点: skill_runner] 执行失败: {e}", "ERROR")
            return {
                "answer": f"技能执行失败: {str(e)}",
                "skill_executed": False,
                "skill_success": False
            }

    def _router_node(self, state: AgentState) -> AgentState:
        """
        路由节点：判断是否需要检索

        Args:
            state: 当前状态（包含 query, session_id, chat_history, feeling）

        Returns:
            更新后的状态（只需返回需要更新的字段）
        """
        query = state["query"]
        self._log(f"[节点: router] 开始执行查询: {query[:30]}...")
        
        need_retrieve = self._rag_workflow.should_retrieve(query)
        self._log(f"[节点: router] 决策: {'需要检索' if need_retrieve else '不需要检索'}")
        
        return {"need_retrieve": need_retrieve}

    def _retrieve_node(self, state: AgentState) -> AgentState:
        """
        检索节点：执行检索

        Args:
            state: 当前状态

        Returns:
            更新后的状态（只需返回 documents）
        """
        query = state["query"]
        self._log(f"[节点: retrieve] 开始执行")
        
        kb = self._rag_workflow.select_knowledge_base(query)
        self._rag_workflow.switch_knowledge_base(kb)
        documents = self._rag_workflow.retrieve(query)
        self._log(f"[节点: retrieve] 检索到 {len(documents)} 个文档")
        
        return {"documents": documents}

    def _generate_node(self, state: AgentState) -> AgentState:
        """
        生成节点：调用 RAG 生成基于文档的回答

        Args:
            state: 当前状态（包含 query, documents, chat_history）

        Returns:
            更新后的状态（返回 RAG 生成的 answer 和成功标志，传给 plan 节点进行任务规划）
        """
        query = state["query"]
        documents = state.get("documents", [])
        self._log(f"[节点: generate] 开始执行，文档数: {len(documents)}")
        
        # RAG 返回结构化结果
        result = self._rag_workflow.generate(query, documents)
        answer = result["answer"]
        rag_success = result["success"]
        
        self._log(f"[节点: generate] RAG 生成完成: {answer[:50]}... (成功: {rag_success})")
        
        return {"answer": answer, "rag_success": rag_success}

    def _plan_node(self, state: AgentState) -> AgentState:
        """
        规划节点：将复杂需求拆分为子任务

        使用责任链模式处理任务生成，支持灵活扩展。

        Args:
            state: 当前状态（包含 query, documents, answer, rag_success, matched_skill）

        Returns:
            更新后的状态（包含子任务队列和初始状态）
        """
        query = state["query"]
        self._log(f"[节点: plan] 开始任务规划")
        
        # 使用责任链模式生成子任务
        chain = TaskGeneratorChain.build()
        subtasks = chain.handle(state, self._task_planner, query)
        
        self._log(f"[节点: plan] 生成 {len(subtasks)} 个子任务")
        for i, task in enumerate(subtasks):
            self._log(f"  [{i+1}] {task['task_description'][:30]}...")
        
        return {
            "subtasks": subtasks,
            "current_task_idx": 0,
            "is_task_completed": False,
            "retry_count": 0,
            "max_retries": self._max_retries,
            "retry_task_idx": -1,
            "is_reflection_passed": False,
            "reflection_feedback": "",
            "reflection_suggestions": [],
            "reflection_confidence": 0.0
        }

    def _execute_task_node(self, state: AgentState) -> AgentState:
        """
        任务执行节点：执行当前子任务

        Args:
            state: 当前状态（包含 subtasks, current_task_idx, retry_count, reflection_suggestions, feeling）

        Returns:
            更新后的状态（包含执行结果）
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        retry_count = state["retry_count"]
        reflection_suggestions = state["reflection_suggestions"]
        feeling = state["feeling"]
        
        current_task = subtasks[current_idx]
        task_desc = current_task["task_description"]
        self._log(f"[节点: execute_task] 执行任务 {current_idx + 1}/{len(subtasks)}: {task_desc[:30]}... (重试次数: {retry_count})")
        
        # 构建任务执行约束
        task_constraint = "\n\n【重要约束】这是计划执行模式，你必须独立完成此任务，不得向用户追问信息。如果任务需要用户提供额外信息才能完成，请基于已有信息自行推断并完成。"
        
        # 如果是重试，加入反思建议
        if retry_count > 0 and reflection_suggestions:
            suggestions_text = "\n".join(f"- {s}" for s in reflection_suggestions)
            enhanced_task = f"请完成以下任务：\n{task_desc}{task_constraint}\n\n改进建议（基于上一次执行反馈）：\n{suggestions_text}"
        else:
            enhanced_task = f"请完成以下任务：\n{task_desc}{task_constraint}"
        
        # 获取 RAG 检索到的文档
        documents = state.get("documents", [])
        
        # 调用 Agent 执行任务
        self._update_prompt_with_feeling(feeling)
        result = self._agent.invoke(enhanced_task, documents, state.get("chat_history", []), feeling)
        task_result = result.get("answer", "")
        
        self._log(f"[节点: execute_task] 任务执行完成: {task_result[:50]}...")
        
        # 更新任务结果
        subtasks[current_idx]["result"] = task_result
        subtasks[current_idx]["status"] = "completed"
        
        return {
            "subtasks": subtasks,
            "answer": task_result,
            "is_task_completed": True
        }

    def _reflect_node(self, state: AgentState) -> AgentState:
        """
        反思校验节点：评估当前任务回答的质量

        Args:
            state: 当前状态（包含 query, answer, documents, subtasks, current_task_idx, retry_count）

        Returns:
            更新后的状态（包含校验结果、反馈、建议、置信度和重试计数）
        """
        query = state["query"]
        answer = state["answer"]
        documents = state.get("documents", [])
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        retry_count = state["retry_count"]
        
        self._log(f"[节点: reflect] 开始反思校验 (重试次数: {retry_count})")
        
        # 获取当前任务描述
        current_task_desc = subtasks[current_idx]["task_description"]
        
        # 执行校验
        result = self._reflection_checker.reflect(current_task_desc, answer, documents)
        is_passed = result["is_passed"]
        feedback = result["feedback"]
        suggestions = result["suggestions"]
        confidence = result["confidence"]
        
        self._log(f"[节点: reflect] 校验结果: {'通过' if is_passed else '未通过'} (置信度: {confidence:.2f})")
        if feedback:
            self._log(f"[节点: reflect] 反馈: {feedback[:50]}...")
        if suggestions:
            self._log(f"[节点: reflect] 改进建议: {len(suggestions)} 条")
        
        return {
            "is_reflection_passed": is_passed,
            "reflection_feedback": feedback,
            "reflection_suggestions": suggestions,
            "reflection_confidence": confidence,
            "retry_count": retry_count + 1 if not is_passed else retry_count,
            "retry_task_idx": current_idx if not is_passed else -1
        }

    def _check_task_complete_node(self, state: AgentState) -> AgentState:
        """
        任务完成检查节点：判断是否有更多任务需要执行

        Args:
            state: 当前状态（包含 subtasks, current_task_idx, answer）

        Returns:
            更新后的状态（汇总最终答案或更新任务索引）
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        answer = state["answer"]
        
        self._log(f"[节点: check_task_complete] 检查任务完成情况")
        
        # 如果已完成所有任务
        if current_idx >= len(subtasks) - 1:
            self._log(f"[节点: check_task_complete] 所有任务已完成")
            # 汇总所有任务结果
            summary = self._task_planner.get_summary(subtasks)
            if summary:
                answer = summary
                self._log(f"[节点: check_task_complete] 生成汇总结果: {summary[:50]}...")
            return {
                "answer": answer,
                "is_task_completed": True,
                "current_task_idx": current_idx
            }
        
        # 还有更多任务
        next_idx = current_idx + 1
        self._log(f"[节点: check_task_complete] 准备执行下一个任务: {next_idx + 1}/{len(subtasks)}")
        
        return {
            "current_task_idx": next_idx,
            "is_task_completed": False,
            "retry_count": 0,
            "is_reflection_passed": False
        }

    def _should_use_skill(self, state: AgentState) -> Literal["skill_runner", "router"]:
        """
        条件路由：判断是否使用匹配到的技能

        Args:
            state: 当前状态（包含 matched_skill）

        Returns:
            "skill_runner" 或 "router"，决定下一步流向
        """
        matched_skill = state.get("matched_skill")
        if matched_skill:
            decision = "skill_runner"
            self._log(f"[条件路由] 匹配到技能，进入技能执行")
        else:
            decision = "router"
            self._log(f"[条件路由] 未匹配到技能，进入检索路由")
        return decision

    def _should_retrieve(self, state: AgentState) -> Literal["retrieve", "plan"]:
        """
        条件路由：判断是否需要检索

        Args:
            state: 当前状态（包含 need_retrieve）

        Returns:
            "retrieve" 或 "plan"，决定下一步流向
        """
        decision = "retrieve" if state["need_retrieve"] else "plan"
        self._log(f"[条件路由] 决策: {decision}")
        return decision

    def _should_retry(self, state: AgentState) -> Literal["retry", "continue"]:
        """
        条件路由：判断是否需要重试

        Args:
            state: 当前状态（包含 is_reflection_passed, retry_count, max_retries）

        Returns:
            "retry" 或 "continue"，决定是否重试当前任务
        """
        is_passed = state["is_reflection_passed"]
        retry_count = state["retry_count"]
        max_retries = state["max_retries"]

        if is_passed:
            decision = "continue"
            self._log(f"[条件路由] 反思校验通过，继续流程")
        elif retry_count < max_retries:
            decision = "retry"
            self._log(f"[条件路由] 反思校验未通过，重试 ({retry_count}/{max_retries})")
        else:
            decision = "continue"
            self._log(f"[条件路由] 已达到最大重试次数 ({max_retries})，终止重试")

        return decision

    def _should_continue_tasks(self, state: AgentState) -> Literal["execute_task", "call_model"]:
        """
        条件路由：判断是否继续执行下一个任务

        Args:
            state: 当前状态（包含 subtasks, current_task_idx, is_task_completed）

        Returns:
            "execute_task" 或 "call_model"，决定下一步流向
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        is_task_completed = state.get("is_task_completed", False)

        # 判断是否所有任务都已执行完成
        # current_idx 是刚执行完的任务索引，需要大于等于最后一个任务索引才算全部完成
        if is_task_completed or current_idx > len(subtasks) - 1:
            decision = "call_model"
            self._log(f"[条件路由] 所有任务已完成，进入最终回答")
        else:
            decision = "execute_task"
            self._log(f"[条件路由] 还有任务未完成，继续执行任务 {current_idx + 1}/{len(subtasks)}")

        return decision

    def _build_enhanced_query(self, query: str, rag_answer: str) -> str:
        """
        构建增强查询

        Args:
            query: 原始查询
            rag_answer: RAG 生成的初步回答

        Returns:
            增强后的查询字符串
        """
        if rag_answer:
            return f"基于以下信息回答问题：\n{rag_answer}\n\n问题：{query}"
        return query

    def _call_model_node(self, state: AgentState) -> AgentState:
        """
        调用模型节点：生成最终回答，更新对话历史

        Args:
            state: 当前状态（包含 query, answer, chat_history, feeling）

        Returns:
            更新后的状态（包含最终回答和更新后的对话历史）
        """
        query = state["query"]
        answer = state["answer"]
        chat_history = state.get("chat_history", [])
        feeling = state["feeling"]
        
        self._log(f"[节点: call_model] 开始执行，回答长度: {len(answer)}，对话历史长度: {len(chat_history)}")
        
        # 如果回答无效，重新调用 Agent
        rag_success = state.get("rag_success", False)
        if not answer or (state.get("need_retrieve", False) and not rag_success):
            self._update_prompt_with_feeling(feeling)
            result = self._agent.invoke(query, None, chat_history, feeling)
            answer = result.get("answer", "")
        
        self._log(f"[节点: call_model] 执行完成: {answer[:50]}...")
        
        result_state = self._update_chat_history(state, query, answer)
        result_state["answer"] = answer
        result_state["feeling"] = feeling
        
        return result_state

    def _update_prompt_with_feeling(self, feeling: Dict[str, Any]):
        """
        根据情绪动态更新 Agent 的 prompt

        Args:
            feeling: 情绪分析结果
        """
        new_prompt = create_prompt(feeling=feeling)
        self._agent.update_prompt(new_prompt)
        self._log(f"[节点: call_model] 已根据情绪更新 prompt: {feeling['feeling']}")

    def _update_chat_history(self, state: AgentState, query: str, answer: str) -> AgentState:
        """
        统一更新对话历史（带裁剪功能）

        Args:
            state: 当前状态
            query: 用户查询
            answer: 生成的回答

        Returns:
            更新后的状态（包含新的对话历史）
        """
        if query and answer:
            self._log(f"[_update_chat_history] 自动更新对话历史")
            chat_history = state.get("chat_history", [])
            new_history = chat_history + [
                HumanMessage(content=query),
                AIMessage(content=answer)
            ]
            
            # 裁剪对话历史，最多保留 10 轮对话（20 条消息）
            max_history_messages = 20
            if len(new_history) > max_history_messages:
                new_history = new_history[-max_history_messages:]
                self._log(f"[_update_chat_history] 对话历史已裁剪，当前长度: {len(new_history)}")
            
            return {"chat_history": new_history}
        return state

    def _build_graph(self):
        """
        构建增强版状态图

        状态图结构：
        START -> feeling_detect -> skill_match -> ┌── 匹配到技能 ──→ skill_runner -> END
                                                 │
                                                 └── 未匹配技能 ──→ router -> ┌── 需要检索 ──→ retrieve -> generate -> plan
                                                                         │                                        │
                                                                         └── 不需要检索 ──→ plan <----------------─┘
                                                                                              |
                                                                                              ▼
                                                                                   execute_task -> check_task_complete -> ┌── 有更多任务 ──→ execute_task
                                                                                                                 │
                                                                                                                 └── 所有任务完成 ──→ call_model -> END
        """
        self._log("开始构建增强版 LangGraph 状态图...")
        
        self._graph = StateGraph(AgentState)

        # 添加节点
        self._graph.add_node("feeling_detect", self._feeling_detect_node)
        self._graph.add_node("skill_match", self._skill_match_node)
        self._graph.add_node("skill_runner", self._skill_runner_node)
        self._graph.add_node("router", self._router_node)
        self._graph.add_node("retrieve", self._retrieve_node)
        self._graph.add_node("generate", self._generate_node)
        self._graph.add_node("plan", self._plan_node)
        self._graph.add_node("execute_task", self._execute_task_node)
        self._graph.add_node("reflect", self._reflect_node)
        self._graph.add_node("check_task_complete", self._check_task_complete_node)
        self._graph.add_node("call_model", self._call_model_node)

        # 基础流程：情绪检测 -> 技能匹配
        self._graph.add_edge(START, "feeling_detect")
        self._graph.add_edge("feeling_detect", "skill_match")

        # 技能匹配分支：匹配到技能走 skill_runner，否则进入检索路由
        self._graph.add_conditional_edges(
            "skill_match",
            self._should_use_skill,
            {"skill_runner": "skill_runner", "router": "router"}
        )

        # 技能执行完成后直接结束
        self._graph.add_edge("skill_runner", END)

        # 路由分支：检索或直接规划
        self._graph.add_conditional_edges(
            "router",
            self._should_retrieve,
            {"retrieve": "retrieve", "plan": "plan"}
        )

        # RAG 路径
        self._graph.add_edge("retrieve", "generate")
        self._graph.add_edge("generate", "plan")

        # 任务执行主路径（暂时跳过 reflect）
        self._graph.add_edge("plan", "execute_task")
        self._graph.add_edge("execute_task", "check_task_complete")

        # 任务完成检查后的条件分支
        self._graph.add_conditional_edges(
            "check_task_complete",
            self._should_continue_tasks,
            {"execute_task": "execute_task", "call_model": "call_model"}
        )

        # 最终路径
        self._graph.add_edge("call_model", END)

        # 编译图
        self._graph = self._graph.compile(checkpointer=self._checkpointer)
        self._log("增强版 LangGraph 状态图构建完成")

    def invoke(self, query: str, session_id: str = "default", uid: Optional[str] = None) -> Dict[str, Any]:
        """
        执行 Agent（标准 LangGraph 调用方式）

        Args:
            query: 用户查询
            session_id: 会话ID
            uid: 用户ID

        Returns:
            包含回答和状态信息的字典
        """
        self._log(f"=== 开始处理请求 ===")
        self._log(f"会话ID: {session_id}")
        self._log(f"用户ID: {uid}")
        self._log(f"用户查询: {query}")

        initial_state: AgentState = {
            "query": query,
            "session_id": session_id,
            "chat_history": [],
            "need_retrieve": False,
            "documents": [],
            "answer": "",
            "feeling": {"feeling": "default", "score": 5},
            "uid": uid,
            "matched_skill": None,
            "skill_executed": False,
            "skill_name": "",
            "skill_success": False,
            "skill_steps": [],
            "subtasks": [],
            "current_task_idx": 0,
            "is_task_completed": False,
            "is_reflection_passed": False,
            "reflection_feedback": "",
            "reflection_suggestions": [],
            "reflection_confidence": 0.0,
            "retry_count": 0,
            "max_retries": self._max_retries,
            "retry_task_idx": -1
        }

        result = self._graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        )

        self._log(f"=== 请求处理完成 ===")
        return {
            "answer": result["answer"],
            "feeling": result["feeling"],
            "reflection_confidence": result["reflection_confidence"],
            "retry_count": result["retry_count"],
            "skill_executed": result.get("skill_executed", False),
            "skill_name": result.get("skill_name", ""),
            "skill_success": result.get("skill_success", False),
            "skill_steps": result.get("skill_steps", [])
        }

    def get_graph(self):
        """
        获取编译后的状态图

        Returns:
            编译后的 StateGraph 对象
        """
        return self._graph
