"""
Skill 引擎
支持目录格式的技能加载和语义匹配
"""

import os
import re
import glob
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np


class SkillEngine:
    """
    Skill 加载和管理引擎

    支持目录格式: skill_name/SKILL.md
    支持 frontmatter 解析
    支持 references 按需加载
    支持基于描述的语义匹配
    """

    def __init__(self, skills_dir: str = None, embedding_client: Any = None):
        if skills_dir is None:
            backend_dir = Path(__file__).parent.parent.parent
            skills_dir = backend_dir / "skills"
        else:
            skills_dir = Path(skills_dir)

        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._embedding_client = embedding_client
        self._skill_embeddings: Dict[str, List[float]] = {}  # 缓存技能描述向量
        self._load_all()
        self._precompute_embeddings()

    def _load_all(self):
        """加载所有 Skill"""
        self._registry.clear()

        if not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            skill_md_alt = skill_dir / "skill.md"
            main_file = skill_md if skill_md.exists() else (skill_md_alt if skill_md_alt.exists() else None)

            if not main_file:
                continue

            try:
                skill = self._load_skill_dir(skill_dir, main_file)
                if skill and skill.get("name"):
                    self._registry[skill["name"]] = skill
                    print(f"[SkillEngine] 加载技能: {skill['name']} - {skill.get('title', '')}")
            except Exception as e:
                print(f"[SkillEngine] 加载技能失败 {skill_dir.name}: {e}")

    def _load_skill_dir(self, skill_dir: Path, main_file: Path) -> Optional[Dict[str, Any]]:
        """加载单个 Skill 目录"""
        content = main_file.read_text(encoding="utf-8")
        skill = self._parse_skill_content(content, skill_dir)

        skill["_path"] = str(skill_dir)
        skill["_main_file"] = main_file.name

        return skill

    def _parse_skill_content(self, content: str, skill_dir: Path) -> Dict[str, Any]:
        """解析 Skill 内容"""
        skill = {
            "name": "",
            "title": "",
            "version": "",
            "author": "",
            "description": "",
            "trigger_keywords": [],
            "difficulty_level": 3,
            "steps": [],
            "tools": [],
            "knowledge": [],
            "output_format": "",
            "references": {},
            "metadata": {}
        }

        frontmatter = self._parse_frontmatter(content)
        if frontmatter:
            skill.update(frontmatter)

        info_pattern = r'- \*\*([^:]+)\*\*:\s*(.+)'
        for match in re.finditer(info_pattern, content):
            key = match.group(1).strip()
            value = match.group(2).strip()

            if key == "名称":
                skill["name"] = value
            elif key == "标题":
                skill["title"] = value
            elif key == "版本":
                skill["version"] = value
            elif key == "作者":
                skill["author"] = value

        desc_match = re.search(r'## 技能描述\n([\s\S]*?)\n## ', content)
        if desc_match:
            skill["description"] = desc_match.group(1).strip()

        keyword_section = re.search(r'### 关键词触发\n([\s\S]*?)\n(?:###|##|$)', content)
        if keyword_section:
            keywords = []
            for line in keyword_section.group(1).strip().split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    keywords.append(line[2:].strip())
            skill["trigger_keywords"] = keywords

        level_match = re.search(r'### 难度等级\n(\d+)', content)
        if level_match:
            skill["difficulty_level"] = int(level_match.group(1))

        steps_section = re.search(r'## 执行流程\n([\s\S]*?)\n(?:## |$)', content)
        if steps_section:
            steps = []
            step_pattern = r'### 步骤(\d+)[：:]\s*([^\n]+)\n([\s\S]*?)(?=\n### 步骤|$)'
            for match in re.finditer(step_pattern, steps_section.group(1)):
                step_info = {
                    "number": int(match.group(1)),
                    "name": match.group(2).strip(),
                    "details": {}
                }
                details_content = match.group(3)
                detail_pattern = r'- \*\*([^:]+)\*\*:\s*(.+)'
                for detail_match in re.finditer(detail_pattern, details_content):
                    detail_key = detail_match.group(1).strip()
                    detail_value = detail_match.group(2).strip()
                    if detail_key == "工具" and detail_value.startswith('['):
                        tools = re.findall(r"'([^']+)'|\"([^\"]+)\"", detail_value)
                        step_info["details"][detail_key] = [t[0] or t[1] for t in tools]
                    else:
                        step_info["details"][detail_key] = detail_value
                steps.append(step_info)
            skill["steps"] = steps

        tools_section = re.search(r'## 工具依赖\n([\s\S]*?)\n(?:## |$)', content)
        if tools_section:
            tools = []
            lines = tools_section.group(1).strip().split('\n')
            header_skipped = False
            for line in lines:
                if not header_skipped:
                    header_skipped = True
                    continue
                parts = line.split('|')
                if len(parts) >= 2:
                    tool_name = parts[1].strip()
                    if tool_name:
                        tools.append(tool_name)
            skill["tools"] = tools

        knowledge_section = re.search(r'## 专业知识\n([\s\S]*?)\n(?:## |$)', content)
        if knowledge_section:
            knowledge = []
            for line in knowledge_section.group(1).strip().split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    knowledge.append(line[2:].strip())
            skill["knowledge"] = knowledge

        format_section = re.search(r'## 输出格式\n```[a-z]*\n([\s\S]*?)```', content)
        if format_section:
            skill["output_format"] = format_section.group(1).strip()

        return skill

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """解析 YAML frontmatter"""
        frontmatter_match = re.match(r'^---\n([\s\S]*?)\n---', content)
        if not frontmatter_match:
            return {}

        import yaml
        try:
            fm = yaml.safe_load(frontmatter_match.group(1))
            if not fm:
                return {}

            result = {}
            if "name" in fm:
                result["name"] = fm["name"]
            if "title" in fm:
                result["title"] = fm["title"]
            if "description" in fm:
                result["description"] = fm["description"]
            if "version" in fm:
                result["version"] = fm["version"]
            if "author" in fm:
                result["author"] = fm["author"]
            if "license" in fm:
                result["license"] = fm["license"]

            if "metadata" in fm:
                result["metadata"] = fm["metadata"]

            return result
        except Exception as e:
            print(f"[SkillEngine] 解析 frontmatter 失败: {e}")
            return {}

    def _precompute_embeddings(self):
        """预计算所有技能描述的嵌入向量"""
        if not self._embedding_client:
            print("[SkillEngine] 未设置嵌入客户端，跳过预计算")
            return

        self._skill_embeddings.clear()
        for skill_name, skill in self._registry.items():
            description = skill.get("description", "")
            if description:
                try:
                    print(f"[SkillEngine] 预计算向量: {skill_name}")
                    embedding = self._embedding_client.embed_query(description)
                    self._skill_embeddings[skill_name] = embedding
                    print(f"[SkillEngine] 预计算成功: {skill_name}, 向量维度: {len(embedding)}")
                except Exception as e:
                    print(f"[SkillEngine] 预计算向量失败 {skill_name}: {e}")
            else:
                print(f"[SkillEngine] {skill_name} 没有描述，跳过")
        
        print(f"[SkillEngine] 预计算完成，共 {len(self._skill_embeddings)} 个技能向量")

    def match(self, query: str, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        根据查询匹配最合适的 Skill

        优先使用语义匹配（基于描述），如果没有嵌入客户端则回退到关键词匹配

        Args:
            query: 用户查询
            threshold: 语义匹配阈值（0-1），低于此阈值不匹配

        Returns:
            匹配到的 Skill 定义，未匹配返回 None
        """
        # 如果有嵌入客户端，使用语义匹配
        if self._embedding_client and self._skill_embeddings:
            try:
                query_embedding = self._embedding_client.embed_query(query)
                if not query_embedding:
                    return self._match_by_keywords(query)

                # 计算与每个技能的相似度
                similarities = []
                query_vec = np.array(query_embedding)
                print(f"[SkillEngine] 查询: '{query}'")
                for skill_name, skill in self._registry.items():
                    skill_embedding = self._skill_embeddings.get(skill_name)
                    if skill_embedding:
                        skill_vec = np.array(skill_embedding)
                        similarity = float(np.dot(query_vec, skill_vec) / 
                                         (np.linalg.norm(query_vec) * np.linalg.norm(skill_vec)))
                        print(f"[SkillEngine] 与 {skill_name} 的相似度: {similarity:.4f}")
                        if similarity >= threshold:
                            similarities.append((skill, similarity))

                if similarities:
                    similarities.sort(key=lambda x: x[1], reverse=True)
                    matched_skill = similarities[0][0]
                    print(f"[SkillEngine] 匹配到技能: {matched_skill['name']} (相似度: {similarities[0][1]:.4f})")
                    return matched_skill
                else:
                    print(f"[SkillEngine] 语义匹配未找到合适技能（阈值: {threshold}），尝试关键词匹配")
                    return self._match_by_keywords(query)
            except Exception as e:
                print(f"[SkillEngine] 语义匹配失败: {e}，回退到关键词匹配")
                return self._match_by_keywords(query)

        # 没有嵌入客户端，使用关键词匹配
        return self._match_by_keywords(query)

    def _match_by_keywords(self, query: str) -> Optional[Dict[str, Any]]:
        """
        基于关键词的匹配（回退方案）

        Args:
            query: 用户查询

        Returns:
            匹配到的 Skill 定义，未匹配返回 None
        """
        matched_skills = []

        for skill_name, skill in self._registry.items():
            keywords = skill.get("trigger_keywords", [])
            if any(keyword in query for keyword in keywords):
                match_count = len([k for k in keywords if k in query])
                matched_skills.append((skill, match_count))
                print(f"[SkillEngine] 关键词匹配: {skill_name} - 匹配数: {match_count}")

        if not matched_skills:
            return None

        matched_skills.sort(key=lambda x: x[1], reverse=True)
        return matched_skills[0][0]

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定名称的 Skill"""
        return self._registry.get(name)

    def list(self) -> List[Dict[str, Any]]:
        """列出所有已加载的 Skills"""
        return list(self._registry.values())

    def reload(self):
        """重新加载所有 Skills"""
        self._load_all()

    def get_reference(self, skill_name: str, ref_path: str) -> Optional[str]:
        """
        获取 Skill 的引用文件内容

        Args:
            skill_name: Skill 名称
            ref_path: 引用文件路径（如 references/diagram-types.md）

        Returns:
            文件内容，未找到返回 None
        """
        skill_dir = self.skills_dir / skill_name
        if not skill_dir.exists():
            return None

        ref_file = skill_dir / ref_path
        if not ref_file.exists():
            ref_file = skill_dir / "references" / os.path.basename(ref_path)

        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8")

        return None

    def generate_prompt(self, skill: Dict[str, Any], query: str) -> str:
        """
        生成 Skill 执行的 prompt

        Args:
            skill: Skill 定义
            query: 用户查询

        Returns:
            生成的 prompt
        """
        steps_desc = ""
        for step in skill.get("steps", []):
            steps_desc += f"{step['number']}. {step['name']}\n"
            for key, value in step.get("details", {}).items():
                if isinstance(value, list):
                    value = ", ".join(value)
                steps_desc += f"   - {key}: {value}\n"

        tools_list = ", ".join(skill.get("tools", []))
        knowledge_desc = "\n".join(f"- {k}" for k in skill.get("knowledge", []))

        prompt = f"""你现在扮演【{skill.get('title', skill.get('name', ''))}】角色。

            技能描述：{skill.get('description', '')}

            执行步骤：
            {steps_desc}

            可用工具：{tools_list if tools_list else '无'}

            专业知识：
            {knowledge_desc if knowledge_desc else '无'}

            用户请求：{query}

            请按照上述步骤执行，必要时调用工具，并输出最终结果。"""

        return prompt


_engine_instance: Optional[SkillEngine] = None


def get_engine(embedding_client: Any = None) -> SkillEngine:
    """获取全局引擎实例
    
    Args:
        embedding_client: 嵌入向量客户端，用于语义匹配（可选）
    
    Returns:
        SkillEngine 实例
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SkillEngine(embedding_client=embedding_client)
    return _engine_instance


def reset_engine():
    """重置引擎实例"""
    global _engine_instance
    _engine_instance = None
