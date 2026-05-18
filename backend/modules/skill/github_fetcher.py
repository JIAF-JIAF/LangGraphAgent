"""
GitHub 仓库内容获取器
用于从 GitHub 获取 Skill 相关文件
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import requests


@dataclass
class GitHubLocation:
    """GitHub 资源定位"""
    type: str  # "repo" 或 "subdir"
    user: str
    repo: str
    branch: str = "main"
    path: str = ""

    @property
    def skill_name(self) -> str:
        if self.path:
            return os.path.basename(self.path)
        return self.repo.replace("-skill", "").replace("-", "_")

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.user}/{self.repo}.git"

    @property
    def raw_base_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}"

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.user}/{self.repo}"


class GitHubFetcher:
    """GitHub 内容获取器"""

    def __init__(self, token: str = None):
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"token {token}"
        self.session.headers["Accept"] = "application/vnd.github.v3+json"

    def parse_url(self, url: str) -> Optional[GitHubLocation]:
        """
        解析 GitHub URL

        支持格式：
        - https://github.com/Agents365-ai/drawio-skill
        - https://github.com/Agents365-ai/drawio-skill/tree/main/skills/drawio-skill
        - git@github.com:Agents365-ai/drawio-skill.git
        """
        url = url.strip()

        # SSH 格式
        ssh_match = re.match(r'git@github\.com:([\w-]+)/([\w-]+)\.git', url)
        if ssh_match:
            user, repo = ssh_match.groups()
            return GitHubLocation(type="repo", user=user, repo=repo)

        # HTTPS 格式
        # https://github.com/user/repo
        # https://github.com/user/repo/tree/branch/path
        # https://github.com/user/repo/blob/branch/path
        parsed = urlparse(url)
        if parsed.netloc != "github.com":
            return None

        parts = parsed.path.strip("/").split("/")

        if len(parts) >= 2:
            user = parts[0]
            repo = parts[1].replace(".git", "")

            if len(parts) >= 4 and parts[2] in ("tree", "blob"):
                branch = parts[3]
                path = "/".join(parts[4:]) if len(parts) > 4 else ""
                return GitHubLocation(type="subdir", user=user, repo=repo, branch=branch, path=path)

            return GitHubLocation(type="repo", user=user, repo=repo)

        return None

    def fetch_file(self, location: GitHubLocation, file_path: str = "", binary: bool = False) -> Optional[Any]:
        """
        获取单个文件内容

        Args:
            location: GitHub 位置
            file_path: 文件路径
            binary: 是否返回二进制内容

        Returns:
            文件内容（字符串或字节）
        """
        if not file_path and location.path:
            file_path = location.path

        if not file_path:
            return None

        raw_url = f"{location.raw_base_url}/{file_path}"

        try:
            response = self.session.get(raw_url, timeout=30)
            if response.status_code == 200:
                if binary:
                    return response.content
                else:
                    # 尝试以文本读取，如果失败则返回 None
                    try:
                        return response.text
                    except UnicodeDecodeError:
                        return None
            return None
        except Exception as e:
            print(f"[GitHubFetcher] 获取文件失败 {raw_url}: {e}")
            return None

    def fetch_directory(self, location: GitHubLocation, path: str = "") -> List[Dict[str, Any]]:
        """
        获取目录内容
        """
        api_path = f"/contents/{path}" if path else "/contents"

        try:
            response = self.session.get(f"{location.api_url}{api_path}?ref={location.branch}", timeout=30)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"[GitHubFetcher] 获取目录失败 {location.api_url}{api_path}: {e}")
            return []

    def find_skill_main_file(self, location: GitHubLocation) -> Optional[str]:
        """
        自动查找 SKILL.md 主文件位置

        查找顺序：
        1. skills/{skill_name}/SKILL.md
        2. {skill_name}/SKILL.md
        3. SKILL.md
        """
        repo_name = location.repo
        skill_name = repo_name.replace("-skill", "").replace("-", "_")

        candidates = [
            f"skills/{repo_name}/SKILL.md",
            f"skills/{repo_name}/skill.md",
            f"{repo_name}/SKILL.md",
            f"{repo_name}/skill.md",
            "SKILL.md",
            "skill.md",
        ]

        for candidate in candidates:
            content = self.fetch_file(location, candidate)
            if content:
                return candidate

        return None

    def fetch_skill_package(self, location: GitHubLocation) -> Optional[Dict[str, Any]]:
        """
        获取完整的 Skill 包

        Returns:
            {
                "name": "drawio-skill",
                "version": "1.0.0",
                "main_file": "skills/drawio-skill/SKILL.md",
                "main_content": "...",
                "files": {
                    "references/diagram-types.md": "...",
                    "scripts/repair_png.py": "..."
                }
            }
        """
        main_file_path = self.find_skill_main_file(location)
        if not main_file_path:
            return None

        main_content = self.fetch_file(location, main_file_path)
        if not main_content:
            return None

        skill_dir = os.path.dirname(main_file_path)
        package = {
            "name": location.skill_name,
            "main_file": main_file_path,
            "main_content": main_content,
            "files": {}
        }

        if skill_dir:
            self._fetch_directory_recursive(location, skill_dir, skill_dir, package)

        version = self._extract_version(main_content)
        if version:
            package["version"] = version

        return package

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

    def _fetch_directory_recursive(self, location: GitHubLocation, current_path: str, base_path: str, package: Dict[str, Any]):
        """
        递归拉取目录内容
        """
        contents = self.fetch_directory(location, current_path)
        for item in contents:
            if item["type"] == "file":
                # 先尝试文本读取
                file_content = self.fetch_file(location, item["path"], binary=False)
                if file_content is not None:
                    # 保存相对于 base_path 的路径
                    relative_path = os.path.relpath(item["path"], base_path)
                    package["files"][relative_path] = file_content
                else:
                    # 文本读取失败，尝试二进制读取
                    file_content_binary = self.fetch_file(location, item["path"], binary=True)
                    if file_content_binary is not None:
                        relative_path = os.path.relpath(item["path"], base_path)
                        package["files"][relative_path] = file_content_binary
            elif item["type"] == "dir":
                # 递归拉取子目录
                self._fetch_directory_recursive(location, item["path"], base_path, package)

    def get_repo_info(self, location: GitHubLocation) -> Optional[Dict[str, Any]]:
        """获取仓库信息"""
        try:
            response = self.session.get(location.api_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("name"),
                    "full_name": data.get("full_name"),
                    "description": data.get("description"),
                    "default_branch": data.get("default_branch"),
                    "stars": data.get("stargazers_count"),
                }
            return None
        except Exception as e:
            print(f"[GitHubFetcher] 获取仓库信息失败: {e}")
            return None
