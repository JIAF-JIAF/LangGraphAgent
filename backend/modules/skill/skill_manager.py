"""
Skill 管理器
统一管理技能的加载、匹配和执行

核心功能：
- 技能加载（从文件系统）
- 技能匹配（关键词/语义）
- 技能执行（步骤化执行）
- 脚本执行（执行 skill 中的脚本文件）
"""

import os
import glob
import re
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field

try:
    from pydantic_ai_skills import Skill, SkillsToolset
    PYDANTIC_AI_SKILLS_AVAILABLE = True
except ImportError:
    PYDANTIC_AI_SKILLS_AVAILABLE = False


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


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


class SkillManager:
    """
    统一的技能管理器
    
    提供完整的技能管理功能：加载、匹配、执行
    """

    def __init__(self, skills_dir: str = "skills", llm_client: Any = None):
        """
        初始化技能管理器
        
        Args:
            skills_dir: 技能文件目录（相对于 backend 目录）
            llm_client: LLM 客户端（用于语义匹配和生成）
        """
        self.skills_dir = skills_dir
        self.llm_client = llm_client
        self.skills: Dict[str, Dict[str, Any]] = {}
        self._load_skills()

    def _load_skills(self):
        """加载所有技能文件"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_path = os.path.join(backend_dir, self.skills_dir)
        
        if not os.path.exists(full_path):
            print(f"[SKILL] 技能目录不存在: {full_path}")
            return

        pattern = os.path.join(full_path, "**", "SKILL.md")
        skill_files = glob.glob(pattern, recursive=True)
        
        print(f"[SKILL] 发现 {len(skill_files)} 个技能文件")
        
        for file_path in skill_files:
            if "SKILL_SPEC" in file_path:
                continue
                
            skill = self._parse_skill_file(file_path)
            if skill and skill.get('name'):
                self.skills[skill['name']] = skill
                print(f"[SKILL] 加载技能: {skill['name']} - {skill['title']}")

    def _parse_skill_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """解析技能文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_skill_content(content, Path(file_path).parent)
        except Exception as e:
            print(f"[SKILL] 解析技能文件失败 {file_path}: {e}")
            return None

    def _parse_skill_content(self, content: str, skill_dir: Path) -> Dict[str, Any]:
        """解析 SKILL.md 内容"""
        import yaml

        result = {
            "name": "",
            "title": "",
            "description": "",
            "version": "unknown",
            "trigger_keywords": [],
            "instructions": "",
            "steps": [],
            "tools": [],
            "knowledge": [],
            "resources": [],
            "scripts": []
        }

        frontmatter_match = re.match(r'^---\n([\s\S]*?)\n---', content)
        if frontmatter_match:
            try:
                frontmatter = yaml.safe_load(frontmatter_match.group(1)) or {}
                result.update(frontmatter)
            except:
                pass

        result["instructions"] = content
        
        result["steps"] = self._extract_steps_from_markdown(content)

        references_dir = skill_dir / "references"
        if references_dir.exists():
            for ref_file in references_dir.iterdir():
                if ref_file.is_file():
                    result["resources"].append({
                        "name": ref_file.name,
                        "path": str(ref_file),
                        "type": "reference"
                    })

        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            for script_file in scripts_dir.iterdir():
                if script_file.is_file():
                    result["scripts"].append({
                        "name": script_file.name,
                        "path": str(script_file),
                        "type": script_file.suffix
                    })

        return result

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

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """获取所有技能列表"""
        return list(self.skills.values())

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定技能"""
        return self.skills.get(name)

    def list(self) -> List[Dict[str, Any]]:
        """获取所有技能列表（兼容旧接口）"""
        return self.get_all_skills()

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定技能（兼容旧接口）"""
        return self.get_skill(name)

    def match(self, query: str) -> Optional[Dict[str, Any]]:
        """匹配技能（兼容旧接口）"""
        return self.match_skill(query)

    def match_skill(self, query: str) -> Optional[Dict[str, Any]]:
        """
        根据用户查询匹配最合适的技能
        
        Args:
            query: 用户查询
            
        Returns:
            匹配到的技能，未匹配返回 None
        """
        if self.llm_client:
            return self._match_by_semantic(query)
        
        return self._match_by_keywords(query)

    def _match_by_semantic(self, query: str) -> Optional[Dict[str, Any]]:
        """基于语义的匹配"""
        try:
            query_embedding = self.llm_client.create_embedding(query)
            if not query_embedding:
                return self._match_by_keywords(query)

            best_match = None
            best_score = -1

            for skill in self.skills.values():
                skill_desc = skill.get("description", "")
                if not skill_desc:
                    continue

                skill_embedding = self.llm_client.create_embedding(skill_desc)
                if not skill_embedding:
                    continue

                import numpy as np
                score = np.dot(query_embedding, skill_embedding)
                if score > best_score:
                    best_score = score
                    best_match = skill

            if best_match and best_score > 0.5:
                return best_match

        except Exception as e:
            print(f"[SKILL] 语义匹配失败: {e}")

        return self._match_by_keywords(query)

    def _match_by_keywords(self, query: str) -> Optional[Dict[str, Any]]:
        """基于关键词的匹配"""
        query_lower = query.lower()
        matched_skills = []
        
        for skill_name, skill in self.skills.items():
            keywords = skill.get('trigger_keywords', [])
            match_count = len([k for k in keywords if k.lower() in query_lower])
            if match_count > 0:
                matched_skills.append((skill, match_count))
        
        if not matched_skills:
            return None
        
        matched_skills.sort(key=lambda x: x[1], reverse=True)
        return matched_skills[0][0]

    def generate_prompt(self, skill: Dict[str, Any], query: str) -> str:
        """
        生成技能专属的 prompt
        
        Args:
            skill: 技能定义
            query: 用户查询
            
        Returns:
            构建好的 prompt
        """
        steps_desc = ""
        for step in skill.get('steps', []):
            steps_desc += f"{step['number']}. {step['name']}\n"
            for key, value in step.get('details', {}).items():
                if isinstance(value, list):
                    value = ", ".join(value)
                steps_desc += f"   - {key}: {value}\n"
        
        tools_list = ", ".join(skill.get('tools', []))
        knowledge_desc = "\n".join(f"- {k}" for k in skill.get('knowledge', []))
        
        prompt = f"""你现在扮演【{skill['title']}】角色。
        
技能描述：{skill['description']}

执行步骤：
{steps_desc}

可用工具：{tools_list}

专业知识：
{knowledge_desc}

用户请求：{query}

请按照上述步骤执行，必要时调用工具，并输出最终结果。"""
        
        return prompt

    def generate_skill_prompt(self, skill: Dict[str, Any], query: str) -> str:
        """生成技能 prompt（兼容旧接口）"""
        return self.generate_prompt(skill, query)

    def execute_script(
        self,
        skill_name: str,
        script_path: str,
        args: List[str] = None,
        env: Dict[str, str] = None,
        cwd: str = None
    ) -> ExecutionResult:
        """
        执行技能脚本
        
        Args:
            skill_name: 技能名称
            script_path: 脚本路径（相对于技能目录）
            args: 脚本参数
            env: 环境变量
            cwd: 工作目录
            
        Returns:
            ExecutionResult 执行结果
        """
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        skill_dir = os.path.join(backend_dir, self.skills_dir, skill_name)
        full_script_path = os.path.join(skill_dir, script_path)

        if not os.path.exists(full_script_path):
            return ExecutionResult(
                success=False,
                error=f"脚本不存在: {script_path}"
            )

        args = args or []
        env = env or {}
        cwd = cwd or skill_dir

        try:
            result = subprocess.run(
                [full_script_path] + args,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, **env},
                cwd=cwd
            )

            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                metadata={
                    "returncode": result.returncode,
                    "script": script_path
                }
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error="脚本执行超时（300秒）"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e)
            )

    def execute_skill(self, skill_name: str, query: str) -> SkillRunResult:
        """
        执行技能（步骤化执行）
        
        Args:
            skill_name: 技能名称
            query: 用户查询
            
        Returns:
            SkillRunResult 运行结果
        """
        start_time = time.time()
        skill = self.get_skill(skill_name)

        if not skill:
            return SkillRunResult(
                skill_name=skill_name,
                success=False,
                error=f"技能不存在: {skill_name}"
            )

        steps = skill.get("steps", [])
        if not steps:
            return self._execute_direct(skill, query, start_time)

        return self._execute_steps(skill, query, steps, start_time)

    def _execute_direct(self, skill: Dict[str, Any], query: str, start_time: float) -> SkillRunResult:
        """无步骤定义时的直接执行"""
        prompt = self.generate_prompt(skill, query)

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
            error="没有配置 LLM 客户端且没有步骤定义"
        )

    def _execute_steps(
        self,
        skill: Dict[str, Any],
        query: str,
        steps: List[Dict[str, Any]],
        start_time: float
    ) -> SkillRunResult:
        """按步骤执行"""
        results: List[StepResult] = []
        context = {"query": query, "variables": {}, "artifacts": {}}

        for step_def in steps:
            step_result = self._execute_step(step_def, context, skill)
            results.append(step_result)

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

        print(f"[SkillManager] 执行步骤 {step_number}: {step_name}")

        try:
            action = step_def.get("action", "prompt")
            details = step_def.get("details", {})

            if action == "script":
                return self._execute_script_step(step_number, step_name, details, context, start_time)
            elif action == "prompt":
                return self._execute_prompt_step(step_number, step_name, details, context, skill, start_time)
            elif action == "condition":
                return self._evaluate_condition(step_number, step_name, details, context, start_time)
            else:
                return StepResult(
                    step_number=step_number,
                    step_name=step_name,
                    status=StepStatus.SKIPPED,
                    error=f"未知操作类型: {action}",
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

        skill_name = context.get("skill_name", "") or context.get("query", "").split()[0]
        result = self.execute_script(
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
            output="没有配置 LLM 客户端",
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
        """渲染模板"""
        def replace_var(match):
            var_path = match.group(1)
            value = self._get_nested_value(context, var_path)
            return str(value) if value is not None else ""

        return re.sub(r'\$\{([^}]+)\}', replace_var, template)

    def _format_output(self, results: List[StepResult]) -> str:
        """格式化步骤输出"""
        outputs = []
        for result in results:
            if result.output:
                outputs.append(f"### {result.step_name}\n{result.output}")
        return "\n\n".join(outputs)

    def reload(self):
        """重新加载所有技能（兼容旧接口）"""
        self.reload_skills()

    def reload_skills(self):
        """重新加载所有技能"""
        self.skills.clear()
        self._load_skills()


# 移除全局单例模式


__all__ = [
    'SkillManager',
    'ExecutionResult',
    'StepResult',
    'StepStatus',
    'SkillRunResult'
]