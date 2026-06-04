"""
skill_save_file 工具

保存生成内容到文件

【功能说明】
将 Agent 生成的内容（如 XML、JSON、Markdown 等）保存到技能的输出目录。
这是技能执行的输出阶段，遵循 Skills as Tools 标准的"输出"阶段。

【调用者】
- LangChain Agent：在 execute_task 节点中，当 Agent 根据指令生成内容后需要保存时调用
- 调用时机：skill_instructions 指示需要生成文件，Agent 完成内容生成后

【消费者】
- LangChain Agent：获取保存结果，确认文件保存成功
- 最终用户：通过前端界面下载或查看生成的文件
- 返回格式：保存路径或错误信息

【工作流程】
1. Agent 通过 skill_instructions 获取指令："生成 DrawIO XML 并保存为 flowchart.drawio"
2. Agent 根据用户需求生成 XML 内容
3. Agent 调用 skill_save_file(
     file_path="flowchart.drawio",
     content="<mxGraph>...</mxGraph>"
   )
4. 文件保存到：./skills/drawio-skill/output/flowchart.drawio（skill_name 从 RunnableConfig 自动获取）
5. 返回："文件已保存: /path/to/flowchart.drawio"

【参数说明】
- file_path: 文件相对路径（必须）
  - 相对于技能目录下的 output/ 目录
  - 示例："flowchart.drawio"、"reports/summary.md"
- content: 文件内容（必须）
  - 由 Agent 生成的文本内容
  - 支持任意文本格式（XML、JSON、Markdown、纯文本等）

注意：skill_name 从 RunnableConfig 自动获取，无需显式传递。

【返回值】
- 成功："文件已保存: {绝对路径}"
- 失败："技能不存在: {skill_name}" 或 "文件保存失败: {错误信息}"

【文件保存位置】
所有文件保存在技能目录的 output/ 子目录下：
```
skills/
└── drawio-skill/
    └── output/
        ├── flowchart.drawio
        ├── diagram.xml
        └── reports/
            └── summary.md
```

【典型使用场景】
- 生成 DrawIO 图表文件（.drawio、.xml）
- 生成报告文档（.md、.pdf）
- 生成配置文件（.json、.yaml）
- 生成代码文件（.py、.js）
"""

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from modules.logger import log, exception
from .factory import SkillToolFactory


class SkillSaveFileInput(BaseModel):
    file_path: str = Field(description="文件路径，如 output/diagram.drawio")
    content: str = Field(description="文件内容")


class SkillSaveFileTool(BaseTool):
    name: str = "skill_save_file"
    description: str = "保存文件到技能输出目录。用于生成内容（如 XML、JSON）并保存到文件系统。"
    args_schema: type[BaseModel] = SkillSaveFileInput
    
    _loader: Any = PrivateAttr()
    
    def __init__(self, loader: Any, **data):
        super().__init__(**data)
        self._loader = loader
    
    def _run(self, file_path: str, content: str, config: RunnableConfig = None) -> str:
        skill_name = config.get("configurable", {}).get("skill_name", "") if config else ""
        log(f"skill_save_file 被调用，skill_name={skill_name}, path={file_path}", module="Skill.Tools")
        skill_dir = self._loader.get_skill_path(skill_name)
        
        if not skill_dir:
            return f"技能不存在: {skill_name}"
        
        output_dir = skill_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 去掉多余的 output/ 前缀（Agent 可能误传）
        clean_path = file_path.lstrip("output/").lstrip("output\\")
        target_path = output_dir / clean_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            target_path.write_text(content, encoding="utf-8")
            log(f"文件保存成功: {target_path}", module="Skill.Tools")
            return f"文件已保存: {target_path}"
        except Exception as e:
            exception(f"文件保存失败: {e}", module="Skill.Tools", exc=e)
            return f"文件保存失败: {str(e)}"


def build_skill_save_file_tool(loader, matcher, executor):
    """
    构建 skill_save_file 工具
    
    Args:
        loader: 技能加载器
        matcher: 技能匹配器
        executor: 技能执行器
        
    Returns:
        skill_save_file 工具实例
    """
    return SkillSaveFileTool(loader=loader)


SkillToolFactory.register("skill_save_file", build_skill_save_file_tool)
