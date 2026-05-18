"""
Skill 安装器
从 GitHub 安装 Skill 到本地目录
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from .github_fetcher import GitHubFetcher, GitHubLocation


@dataclass
class InstallResult:
    """安装结果"""
    success: bool
    message: str
    skill_name: str = ""
    version: str = ""
    installed_path: str = ""


class SkillInstaller:
    """Skill 安装器"""

    def __init__(self, skills_dir: str = None, token: str = None):
        if skills_dir is None:
            backend_dir = Path(__file__).parent.parent.parent
            skills_dir = backend_dir / "skills"
        else:
            skills_dir = Path(skills_dir)

        self.skills_dir = skills_dir
        self.fetcher = GitHubFetcher(token=token)
        self._ensure_skills_dir()

    def _ensure_skills_dir(self):
        """确保 skills 目录存在"""
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def install_from_url(self, url: str) -> InstallResult:
        """
        从 GitHub URL 安装 Skill

        Args:
            url: GitHub 仓库 URL

        Returns:
            InstallResult 安装结果
        """
        location = self.fetcher.parse_url(url)
        if not location:
            return InstallResult(
                success=False,
                message=f"无法解析 GitHub URL: {url}"
            )

        package = self.fetcher.fetch_skill_package(location)
        if not package:
            return InstallResult(
                success=False,
                message=f"无法获取 Skill 内容，请检查 URL 是否正确"
            )

        skill_name = package["name"]
        target_dir = self.skills_dir / skill_name

        if target_dir.exists():
            return InstallResult(
                success=False,
                message=f"Skill '{skill_name}' 已存在，请先删除后再安装"
            )

        return self._save_skill_package(skill_name, package, target_dir)

    def uninstall(self, skill_name: str) -> InstallResult:
        """
        卸载 Skill

        Args:
            skill_name: Skill 名称

        Returns:
            InstallResult 卸载结果
        """
        target_dir = self.skills_dir / skill_name

        if not target_dir.exists():
            return InstallResult(
                success=False,
                message=f"Skill '{skill_name}' 不存在"
            )

        try:
            shutil.rmtree(target_dir)
            return InstallResult(
                success=True,
                message=f"Skill '{skill_name}' 已卸载",
                skill_name=skill_name
            )
        except Exception as e:
            return InstallResult(
                success=False,
                message=f"卸载失败: {str(e)}"
            )

    def list_installed(self) -> list:
        """
        列出已安装的 Skills

        Returns:
            [{id, name, title, file, version, description}]
        """
        if not self.skills_dir.exists():
            return []

        installed = []
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                skill_md_alt = item / "skill.md"
                main_file = skill_md if skill_md.exists() else (skill_md_alt if skill_md_alt.exists() else None)

                title = item.name
                description = ""
                version = "未知"
                file_name = main_file.name if main_file else ""

                if main_file:
                    try:
                        content = main_file.read_text(encoding="utf-8")
                        version = self._extract_version(content) or "未知"
                        description = self._extract_description(content)
                        # 尝试从 SKILL.md 中提取标题
                        title = self._extract_title(content) or item.name
                    except Exception:
                        pass

                skill_info = {
                    "id": item.name,
                    "name": item.name,
                    "title": title,
                    "file": file_name,
                    "version": version,
                    "description": description
                }

                installed.append(skill_info)

        return installed

    def _extract_title(self, content: str) -> Optional[str]:
        """从 SKILL.md 内容中提取标题"""
        import re
        # 匹配以 # 开头的标题行
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return None

    def _save_skill_package(self, skill_name: str, package: Dict[str, Any],
                            target_dir: Path) -> InstallResult:
        """
        保存 Skill 包到目录
        """
        try:
            target_dir.mkdir(parents=True, exist_ok=True)

            main_content = package.get("main_content", "")
            main_file_path = package.get("main_file", "SKILL.md")
            main_file_name = os.path.basename(main_file_path)

            (target_dir / main_file_name).write_text(main_content, encoding="utf-8")

            files = package.get("files", {})
            for file_path, content in files.items():
                file_full_path = target_dir / file_path
                file_full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 检查是否是二进制内容
                if isinstance(content, bytes):
                    file_full_path.write_bytes(content)
                else:
                    file_full_path.write_text(content, encoding="utf-8")

            version = package.get("version", "未知")

            return InstallResult(
                success=True,
                message=f"Skill '{skill_name}' 安装成功",
                skill_name=skill_name,
                version=version,
                installed_path=str(target_dir)
            )

        except Exception as e:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            return InstallResult(
                success=False,
                message=f"安装失败: {str(e)}"
            )

    def _extract_version(self, content: str) -> Optional[str]:
        """从 SKILL.md 内容中提取版本号"""
        import re
        patterns = [
            r'version:\s*["\']?(\d+\.\d+\.\d+)["\']?',
            r'##\s+版本\s+(\d+\.\d+\.\d+)',
            r'v(\d+\.\d+\.\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        return None

    def _extract_description(self, content: str) -> str:
        """从 SKILL.md 内容中提取描述"""
        import re
        patterns = [
            r'description:\s*["\']([^"\']+)["\']',
            r'##\s+技能描述\s*\n\s*([^\n]+)',
            r'#\s+[^\n]+\s*\n\s*([^\n#]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                desc = match.group(1).strip()
                return desc[:100] + "..." if len(desc) > 100 else desc
        return ""


class SkillManagerAdapter:
    """
    SkillEngine 与旧版 SkillManager 接口的适配器

    供 LangGraphAgent 使用，保持向后兼容
    """

    def __init__(self, skill_engine):
        self._engine = skill_engine

    def get_all_skills(self):
        """获取所有技能"""
        return self._engine.list()

    def get_skill(self, name):
        """获取指定技能"""
        return self._engine.get(name)

    def match_skill(self, query):
        """匹配技能"""
        return self._engine.match(query)

    def generate_skill_prompt(self, skill, query):
        """生成技能 prompt"""
        return self._engine.generate_prompt(skill, query)

    def reload_skills(self):
        """重新加载"""
        self._engine.reload()


_installer_instance: Optional[SkillInstaller] = None


def get_installer() -> SkillInstaller:
    """获取全局安装器实例"""
    global _installer_instance
    if _installer_instance is None:
        _installer_instance = SkillInstaller()
    return _installer_instance
