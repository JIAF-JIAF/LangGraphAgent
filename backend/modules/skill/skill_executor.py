"""
Skill Executor - 基于 pydantic-ai-skills 的标准化 Skill 执行器
支持渐进式加载、脚本执行和 Skill 管理
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

import yaml

try:
    from pydantic_ai_skills import Skill, SkillsToolset, SkillsCapability
    from pydantic_ai_skills.models import SkillMetadata, SkillScript
    PYDANTIC_AI_SKILLS_AVAILABLE = True
except ImportError:
    PYDANTIC_AI_SKILLS_AVAILABLE = False
    Skill = None
    SkillsToolset = None
    SkillsCapability = None


@dataclass
class ExecutionResult:
    """Skill 执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillExecutor:
    """
    标准化 Skill 执行器

    特性：
    - 渐进式加载（Progressive Disclosure）
    - 脚本安全执行
    - 与现有 SkillEngine 兼容
    """

    def __init__(
        self,
        skills_dir: str = None,
        llm_client: Any = None,
        timeout: int = 300
    ):
        """
        初始化 Skill 执行器

        Args:
            skills_dir: Skills 目录路径
            llm_client: LLM 客户端（用于生成提示）
            timeout: 脚本执行超时时间（秒）
        """
        if skills_dir is None:
            backend_dir = Path(__file__).parent.parent.parent
            skills_dir = backend_dir / "skills"
        else:
            skills_dir = Path(skills_dir)

        self.skills_dir = skills_dir
        self.llm_client = llm_client
        self.timeout = timeout
        self._toolset: Optional[Any] = None

        if PYDANTIC_AI_SKILLS_AVAILABLE:
            self._init_toolset()

    def _init_toolset(self):
        """初始化 pydantic-ai-skills Tools"""
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)

        self._toolset = SkillsToolset(
            skills_dir=str(self.skills_dir),
            include_version=True
        )
        print(f"[SkillExecutor] Tools 初始化完成, 目录: {self.skills_dir}")

    def list_skills(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的 Skills

        Returns:
            Skill 元数据列表
        """
        if self._toolset:
            skills = self._toolset.list_skills()
            return [
                {
                    "name": s.name,
                    "description": s.description,
                    "version": getattr(s, 'version', 'unknown'),
                    "metadata": getattr(s, 'metadata', {})
                }
                for s in skills
            ]

        return self._list_skills_fallback()

    def _list_skills_fallback(self) -> List[Dict[str, Any]]:
        """不支持 pydantic-ai-skills 时的回退方案"""
        skills = []
        if not self.skills_dir.exists():
            return skills

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                metadata = self._extract_frontmatter(content)
                skills.append({
                    "name": metadata.get("name", skill_dir.name),
                    "description": metadata.get("description", ""),
                    "version": metadata.get("version", "unknown"),
                    "path": str(skill_dir)
                })
            except Exception as e:
                print(f"[SkillExecutor] 读取 skill 失败 {skill_dir.name}: {e}")

        return skills

    def _extract_frontmatter(self, content: str) -> Dict[str, Any]:
        """提取 YAML frontmatter"""
        match = yaml.match(r'^---\n([\s\S]*?)\n---', content)
        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except:
                return {}
        return {}

    def load_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        加载完整的 Skill 定义

        Args:
            skill_name: Skill 名称

        Returns:
            Skill 定义字典
        """
        if self._toolset:
            try:
                skill = self._toolset.load_skill(skill_name)
                if skill:
                    return self._skill_to_dict(skill)
            except Exception as e:
                print(f"[SkillExecutor] 加载 skill 失败 {skill_name}: {e}")

        return self._load_skill_fallback(skill_name)

    def _load_skill_fallback(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """回退方案：直接从文件系统加载"""
        skill_dir = self.skills_dir / skill_name
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")
            return self._parse_skill_content(content, skill_dir)
        except Exception as e:
            print(f"[SkillExecutor] 加载 skill 失败 {skill_name}: {e}")
            return None

    def _skill_to_dict(self, skill: Any) -> Dict[str, Any]:
        """将 pydantic-ai-skills Skill 对象转换为字典"""
        return {
            "name": skill.name,
            "description": skill.description,
            "version": getattr(skill, 'version', 'unknown'),
            "instructions": getattr(skill, 'instructions', ''),
            "metadata": getattr(skill, 'metadata', {}),
            "resources": getattr(skill, 'resources', []),
            "scripts": getattr(skill, 'scripts', [])
        }

    def _parse_skill_content(self, content: str, skill_dir: Path) -> Dict[str, Any]:
        """解析 SKILL.md 内容"""
        import re

        result = {
            "name": "",
            "description": "",
            "instructions": "",
            "version": "unknown",
            "resources": [],
            "scripts": []
        }

        frontmatter = self._extract_frontmatter(content)
        result.update(frontmatter)

        result["instructions"] = content

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

    def execute_script(
        self,
        skill_name: str,
        script_path: str,
        args: List[str] = None,
        env: Dict[str, str] = None,
        cwd: str = None
    ) -> ExecutionResult:
        """
        执行 Skill 脚本

        Args:
            skill_name: Skill 名称
            script_path: 脚本路径（相对于 skill 目录）
            args: 脚本参数
            env: 环境变量
            cwd: 工作目录

        Returns:
            ExecutionResult 执行结果
        """
        skill_dir = self.skills_dir / skill_name
        full_script_path = skill_dir / script_path

        if not full_script_path.exists():
            return ExecutionResult(
                success=False,
                error=f"脚本不存在: {script_path}"
            )

        args = args or []
        env = env or {}
        cwd = cwd or str(skill_dir)

        try:
            result = subprocess.run(
                [str(full_script_path)] + args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
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
                error=f"脚本执行超时（{self.timeout}秒）"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e)
            )

    def generate_prompt(self, skill: Dict[str, Any], query: str) -> str:
        """
        生成 Skill 执行的 prompt

        Args:
            skill: Skill 定义
            query: 用户查询

        Returns:
            生成的 prompt
        """
        instructions = skill.get("instructions", "")
        description = skill.get("description", "")
        name = skill.get("name", "")

        prompt = f"""你正在使用技能: {name}

技能描述: {description}

技能说明:
{instructions}

用户请求: {query}

请按照技能说明执行任务。"""

        return prompt

    def match_skill(self, query: str) -> Optional[Dict[str, Any]]:
        """
        根据查询匹配最合适的 Skill

        Args:
            query: 用户查询

        Returns:
            匹配的 Skill 定义，未匹配返回 None
        """
        skills = self.list_skills()
        if not skills:
            return None

        if self.llm_client:
            return self._match_by_embedding(query, skills)
        else:
            return self._match_by_keywords(query, skills)

    def _match_by_embedding(self, query: str, skills: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """基于嵌入向量的语义匹配"""
        try:
            query_embedding = self.llm_client.create_embedding(query)
            if not query_embedding:
                return self._match_by_keywords(query, skills)

            best_match = None
            best_score = -1

            for skill in skills:
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
                return self.load_skill(best_match["name"])

        except Exception as e:
            print(f"[SkillExecutor] 语义匹配失败: {e}")

        return self._match_by_keywords(query, skills)

    def _match_by_keywords(self, query: str, skills: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """基于关键词的简单匹配"""
        query_lower = query.lower()
        best_match = None
        best_score = 0

        for skill in skills:
            name = skill.get("name", "").lower()
            desc = skill.get("description", "").lower()
            keywords = f"{name} {desc}".split()

            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_match = skill

        if best_match:
            return self.load_skill(best_match["name"])

        return None


_executor_instance: Optional[SkillExecutor] = None


def get_executor(llm_client: Any = None, skills_dir: str = None) -> SkillExecutor:
    """
    获取全局 SkillExecutor 实例

    Args:
        llm_client: LLM 客户端
        skills_dir: Skills 目录路径

    Returns:
        SkillExecutor 实例
    """
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = SkillExecutor(
            skills_dir=skills_dir,
            llm_client=llm_client
        )
    return _executor_instance


def reset_executor():
    """重置执行器实例"""
    global _executor_instance
    _executor_instance = None


__all__ = [
    'SkillExecutor',
    'ExecutionResult',
    'get_executor',
    'reset_executor'
]