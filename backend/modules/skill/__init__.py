"""
Skill 模块 - 统一的技能管理模块

提供完整的技能管理功能：
- 技能加载（从文件系统）
- 技能匹配（关键词/语义）
- 技能执行（步骤化执行）
- 脚本执行（执行 skill 中的脚本文件）
"""

# 核心管理器
from .skill_manager import (
    SkillManager,
    ExecutionResult,
    StepResult,
    StepStatus,
    SkillRunResult
)

# 兼容性导出（保持旧接口）
from .skill_engine import SkillEngine
from .skill_manager import SkillManager as LegacySkillManager
from .installer import SkillInstaller
from .github_fetcher import GitHubFetcher
from .md_parser import SkillParser


def get_engine() -> SkillEngine:
    """获取技能引擎（兼容旧接口）"""
    return SkillEngine()


__all__ = [
    # 新接口
    'SkillManager',
    'ExecutionResult',
    'StepResult',
    'StepStatus',
    'SkillRunResult',
    
    # 旧接口（兼容）
    'SkillEngine',
    'SkillInstaller',
    'GitHubFetcher',
    'SkillParser',
    'get_engine'
]