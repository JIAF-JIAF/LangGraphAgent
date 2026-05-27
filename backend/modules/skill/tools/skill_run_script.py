"""
skill_run_script 工具

执行技能脚本

【功能说明】
执行技能目录下的脚本文件（如 Python 脚本、Shell 脚本等）。
这是技能执行的执行阶段，遵循 Skills as Tools 标准的"执行"阶段。

【调用者】
- LangChain Agent：在 execute_task 节点中，当技能指令要求执行脚本时调用
- 调用时机：skill_instructions 指示需要执行脚本处理数据或生成内容

【消费者】
- LangChain Agent：获取脚本执行结果（标准输出）
- 最终用户：通过脚本生成的文件或数据
- 返回格式：脚本的 stdout 输出或错误信息

【工作流程】
1. Agent 通过 skill_instructions 获取指令："执行 scripts/process_data.py 处理数据"
2. Agent 调用 skill_run_script(
     script_path="scripts/process_data.py",
     args="--input data.csv --output result.json",
     timeout=60
   )
3. 脚本在当前技能目录下执行（skill_name 从上下文自动获取）
4. 返回脚本的 stdout 输出："数据处理完成，已生成 result.json"

【参数说明】
- script_path: 脚本相对路径（必须）
  - 相对于技能目录
  - 示例："scripts/process.py"、"tools/generate.sh"
- args: 脚本参数（可选）
  - 空格分隔的参数字符串
  - 示例："--input data.csv --output result.json"
- timeout: 超时时间（可选，默认 30 秒）
  - 脚本执行的最大等待时间
  - 超时后自动终止脚本

注意：skill_name 从上下文自动获取，无需显式传递。

【返回值】
- 成功：脚本的 stdout 输出内容
- 失败："脚本执行失败: {错误信息}"
- 超时："脚本执行失败: 执行超时"

【执行环境】
- 工作目录：技能目录（./skills/{skill_name}/）
- Python 环境：系统 Python 环境
- 权限：继承当前进程权限
- 隔离：每个脚本在独立进程中执行

【典型使用场景】
- 数据处理脚本：处理 CSV、JSON 等数据文件
- 文件转换脚本：转换格式（如 Markdown 转 PDF）
- 第三方工具调用：调用命令行工具
- 复杂计算：执行需要本地环境的计算任务

【注意事项】
- 仅当 skill_instructions 明确要求时才调用
- 脚本必须在技能目录下存在
- 脚本应具有可执行权限
- 长时间运行的任务应设置合适的 timeout
"""

from typing import Any
from pydantic import BaseModel, Field, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from modules.logger import log
from .factory import SkillToolFactory


class SkillScriptInput(BaseModel):
    script_path: str = Field(description="脚本路径，如 scripts/process.py")
    args: str = Field(default="", description="脚本参数，空格分隔")
    timeout: int = Field(default=30, description="超时时间（秒）")


class SkillRunScriptTool(BaseTool):
    name: str = "skill_run_script"
    description: str = "执行技能脚本。仅当技能指令要求执行脚本时调用，脚本在隔离的工作目录中运行。"
    args_schema: type[BaseModel] = SkillScriptInput
    
    _executor: Any = PrivateAttr()
    
    def __init__(self, executor: Any, **data):
        super().__init__(**data)
        self._executor = executor
    
    def _run(
        self,
        script_path: str,
        args: str = "",
        timeout: int = 30,
        config: RunnableConfig = None,
    ) -> str:
        log(f"skill_run_script 被调用，script={script_path}", module="Skill.Tools")
        
        skill_name = config.get("configurable", {}).get("skill_name", "") if config else ""
        
        if not skill_name:
            return "错误：config 中未设置技能名称，无法执行脚本。"
        
        arg_list = args.split() if args else []
        result = self._executor.run_script(skill_name, script_path, args=arg_list, timeout=timeout)
        
        if result["success"]:
            output = result.get("output", "")
            
            if not output and result.get("stdout"):
                output = result["stdout"]
            
            return output or "脚本执行成功（无输出）"
        
        error = result.get("error", "未知错误")
        return f"脚本执行失败: {error}"


def build_skill_run_script_tool(loader, matcher, executor):
    """
    构建 skill_run_script 工具
    
    Args:
        loader: 技能加载器
        matcher: 技能匹配器
        executor: 技能执行器
        
    Returns:
        skill_run_script 工具实例
    """
    return SkillRunScriptTool(executor=executor)


SkillToolFactory.register("skill_run_script", build_skill_run_script_tool)
