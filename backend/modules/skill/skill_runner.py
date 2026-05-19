"""
Skill Runner - Skill 工作流执行器
负责执行完整的 Skill 流程，包括步骤执行、状态管理和结果收集
"""

import re
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .skill_executor import SkillExecutor, ExecutionResult, get_executor


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """步骤执行结果"""
    step_number: int
    step_name: str
    status: StepStatus
    output: str = ""
    error: str = ""
    duration: float = 0
    artifacts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SkillRunResult:
    """Skill 运行结果"""
    skill_name: str
    success: bool
    steps: List[StepResult] = field(default_factory=list)
    final_output: str = ""
    error: str = ""
    total_duration: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillRunner:
    """
    Skill 工作流执行器

    功能：
    - 解析 SKILL.md 中的执行步骤
    - 按顺序执行步骤
    - 支持步骤跳过和重试
    - 收集执行结果和产物
    """

    def __init__(
        self,
        executor: SkillExecutor = None,
        llm_client: Any = None,
        callback: Callable[[str, Any], None] = None
    ):
        """
        初始化 Skill Runner

        Args:
            executor: SkillExecutor 实例
            llm_client: LLM 客户端
            callback: 步骤执行回调函数 (step_name, result) -> None
        """
        self.executor = executor or get_executor(llm_client=llm_client)
        self.llm_client = llm_client
        self.callback = callback
        self._steps_cache: Dict[str, List[Dict[str, Any]]] = {}

    def run(self, skill_name: str, query: str, **kwargs) -> SkillRunResult:
        """
        运行 Skill

        Args:
            skill_name: Skill 名称
            query: 用户查询
            **kwargs: 额外参数（如上下文变量）

        Returns:
            SkillRunResult 运行结果
        """
        start_time = time.time()
        skill = self.executor.load_skill(skill_name)

        if not skill:
            return SkillRunResult(
                skill_name=skill_name,
                success=False,
                error=f"Skill not found: {skill_name}"
            )

        steps = self._parse_steps(skill)
        if not steps:
            return self._run_direct(skill, query, start_time)

        return self._run_steps(skill, query, steps, start_time, **kwargs)

    def _run_direct(
        self,
        skill: Dict[str, Any],
        query: str,
        start_time: float
    ) -> SkillRunResult:
        """无步骤定义时的直接执行"""
        prompt = self.executor.generate_prompt(skill, query)

        if self.llm_client:
            try:
                response = self.llm_client.chat.invoke(prompt)
                output = response.content if hasattr(response, 'content') else str(response)

                return SkillRunResult(
                    skill_name=skill.get("name", ""),
                    success=True,
                    final_output=output,
                    total_duration=time.time() - start_time
                )
            except Exception as e:
                return SkillRunResult(
                    skill_name=skill.get("name", ""),
                    success=False,
                    error=str(e),
                    total_duration=time.time() - start_time
                )

        return SkillRunResult(
            skill_name=skill.get("name", ""),
            success=False,
            error="No LLM client configured and no steps to execute"
        )

    def _run_steps(
        self,
        skill: Dict[str, Any],
        query: str,
        steps: List[Dict[str, Any]],
        start_time: float,
        **kwargs
    ) -> SkillRunResult:
        """按步骤执行"""
        results: List[StepResult] = []
        context = {"query": query, "variables": kwargs, "artifacts": {}}

        for step_def in steps:
            step_result = self._execute_step(
                step_def, context, skill
            )
            results.append(step_result)

            if self.callback:
                self.callback(step_def.get("name", ""), step_result)

            if step_result.status == StepStatus.FAILED:
                return SkillRunResult(
                    skill_name=skill.get("name", ""),
                    success=False,
                    steps=results,
                    error=step_result.error,
                    total_duration=time.time() - start_time
                )

        return SkillRunResult(
            skill_name=skill.get("name", ""),
            success=True,
            steps=results,
            final_output=self._format_output(results),
            total_duration=time.time() - start_time
        )

    def _execute_step(
        self,
        step_def: Dict[str, Any],
        context: Dict[str, Any],
        skill: Dict[str, Any]
    ) -> StepResult:
        """执行单个步骤"""
        step_name = step_def.get("name", "Unknown")
        step_number = step_def.get("number", 0)
        start_time = time.time()

        print(f"[SkillRunner] 执行步骤 {step_number}: {step_name}")

        try:
            action = step_def.get("action", "prompt")
            details = step_def.get("details", {})

            if action == "script":
                return self._execute_script_step(
                    step_number, step_name, details, context, start_time
                )
            elif action == "prompt":
                return self._execute_prompt_step(
                    step_number, step_name, details, context, skill, start_time
                )
            elif action == "condition":
                return self._evaluate_condition(
                    step_number, step_name, details, context, start_time
                )
            else:
                return StepResult(
                    step_number=step_number,
                    step_name=step_name,
                    status=StepStatus.SKIPPED,
                    error=f"Unknown action type: {action}",
                    duration=time.time() - start_time
                )

        except Exception as e:
            return StepResult(
                step_number=step_number,
                step_name=step_name,
                status=StepStatus.FAILED,
                error=str(e),
                duration=time.time() - start_time
            )

    def _execute_script_step(
        self,
        step_number: int,
        step_name: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
        start_time: float
    ) -> StepResult:
        """执行脚本步骤"""
        script = details.get("script", "")
        args = details.get("args", [])
        env = details.get("env", {})

        skill_name = context.get("skill_name", "")
        result = self.executor.execute_script(
            skill_name=skill_name,
            script_path=script,
            args=args,
            env=env
        )

        return StepResult(
            step_number=step_number,
            step_name=step_name,
            status=StepStatus.COMPLETED if result.success else StepStatus.FAILED,
            output=result.output,
            error=result.error,
            duration=time.time() - start_time,
            artifacts=result.artifacts
        )

    def _execute_prompt_step(
        self,
        step_number: int,
        step_name: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
        skill: Dict[str, Any],
        start_time: float
    ) -> StepResult:
        """执行 LLM prompt 步骤"""
        prompt_template = details.get("prompt", "")
        output_key = details.get("output_key", f"step_{step_number}_output")

        prompt = self._render_template(prompt_template, context)

        if self.llm_client:
            try:
                response = self.llm_client.chat.invoke(prompt)
                output = response.content if hasattr(response, 'content') else str(response)

                context["variables"][output_key] = output

                return StepResult(
                    step_number=step_number,
                    step_name=step_name,
                    status=StepStatus.COMPLETED,
                    output=output,
                    duration=time.time() - start_time
                )
            except Exception as e:
                return StepResult(
                    step_number=step_number,
                    step_name=step_name,
                    status=StepStatus.FAILED,
                    error=str(e),
                    duration=time.time() - start_time
                )

        return StepResult(
            step_number=step_number,
            step_name=step_name,
            status=StepStatus.SKIPPED,
            output="No LLM client configured",
            duration=time.time() - start_time
        )

    def _evaluate_condition(
        self,
        step_number: int,
        step_name: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
        start_time: float
    ) -> StepResult:
        """评估条件步骤"""
        condition = details.get("condition", "")
        true_action = details.get("then", [])
        false_action = details.get("else", [])

        try:
            condition_met = self._evaluate_condition_expr(condition, context)

            action = true_action if condition_met else false_action
            outputs = []
            for sub_step in action:
                result = self._execute_step(sub_step, context, {})
                outputs.append(result.output)

            return StepResult(
                step_number=step_number,
                step_name=step_name,
                status=StepStatus.COMPLETED,
                output="\n".join(outputs),
                duration=time.time() - start_time
            )
        except Exception as e:
            return StepResult(
                step_number=step_number,
                step_name=step_name,
                status=StepStatus.FAILED,
                error=str(e),
                duration=time.time() - start_time
            )

    def _evaluate_condition_expr(self, expr: str, context: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        expr = expr.strip()

        if expr.startswith("${") and expr.endswith("}"):
            var_path = expr[2:-1]
            value = self._get_nested_value(context, var_path)
            return bool(value)

        if "==" in expr:
            parts = expr.split("==")
            left = self._resolve_value(parts[0].strip(), context)
            right = self._resolve_value(parts[1].strip(), context)
            return left == right

        if "!=" in expr:
            parts = expr.split("!=")
            left = self._resolve_value(parts[0].strip(), context)
            right = self._resolve_value(parts[1].strip(), context)
            return left != right

        return bool(expr)

    def _resolve_value(self, value: str, context: Dict[str, Any]) -> Any:
        """解析变量值"""
        if value.startswith("${") and value.endswith("}"):
            return self._get_nested_value(context, value[2:-1])
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        return value

    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """获取嵌套字典的值"""
        keys = path.split(".")
        value = obj
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """渲染 prompt 模板"""
        def replace_var(match):
            var_path = match.group(1)
            value = self._get_nested_value(context, var_path)
            return str(value) if value is not None else ""

        return re.sub(r'\$\{([^}]+)\}', replace_var, template)

    def _parse_steps(self, skill: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析 SKILL.md 中的步骤定义"""
        skill_name = skill.get("name", "")
        if skill_name in self._steps_cache:
            return self._steps_cache[skill_name]

        instructions = skill.get("instructions", "")
        steps = self._extract_steps_from_markdown(instructions)

        self._steps_cache[skill_name] = steps
        return steps

    def _extract_steps_from_markdown(self, content: str) -> List[Dict[str, Any]]:
        """从 Markdown 内容中提取步骤"""
        steps = []

        step_pattern = r'###\s*步骤\s*(\d+)\s*[:：]?\s*(.+?)\n([\s\S]*?)(?=\n###|\n##|$)'
        for match in re.finditer(step_pattern, content):
            step_num = int(match.group(1))
            step_name = match.group(2).strip()
            step_content = match.group(3)

            step_def = {
                "number": step_num,
                "name": step_name,
                "action": "prompt",
                "details": {}
            }

            tool_match = re.search(r'\*\*工具\*\*:\s*(.+)', step_content)
            if tool_match:
                step_def["details"]["tools"] = tool_match.group(1).strip()

            prompt_match = re.search(r'\*\*Prompt\*\*:\s*([\s\S]+?)(?=\n\*\*|$)', step_content)
            if prompt_match:
                step_def["action"] = "prompt"
                step_def["details"]["prompt"] = prompt_match.group(1).strip()

            script_match = re.search(r'\*\*脚本\*\*:\s*(.+)', step_content)
            if script_match:
                step_def["action"] = "script"
                step_def["details"]["script"] = script_match.group(1).strip()

            condition_match = re.search(r'\*\*条件\*\*:\s*(.+)', step_content)
            if condition_match:
                step_def["action"] = "condition"
                step_def["details"]["condition"] = condition_match.group(1).strip()

            steps.append(step_def)

        return sorted(steps, key=lambda x: x["number"])

    def _format_output(self, results: List[StepResult]) -> str:
        """格式化步骤输出"""
        outputs = []
        for result in results:
            if result.output:
                outputs.append(f"### {result.step_name}\n{result.output}")

        return "\n\n".join(outputs)


_runner_instance: Optional[SkillRunner] = None


def get_runner(llm_client: Any = None) -> SkillRunner:
    """
    获取全局 SkillRunner 实例

    Args:
        llm_client: LLM 客户端

    Returns:
        SkillRunner 实例
    """
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = SkillRunner(llm_client=llm_client)
    return _runner_instance


def reset_runner():
    """重置 Runner 实例"""
    global _runner_instance
    _runner_instance = None


__all__ = [
    'SkillRunner',
    'StepResult',
    'StepStatus',
    'SkillRunResult',
    'get_runner',
    'reset_runner'
]