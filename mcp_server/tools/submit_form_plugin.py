"""
表单提交工具插件
"""

from typing import Optional
from mcp_server.tools.registry import register_tool
from mcp_server.logger import info


@register_tool(
    name="submit_form",
    description="提交客户咨询表单，记录客户信息和咨询内容",
    parameters=[
        {
            "name": "name",
            "type": "string",
            "description": "客户姓名",
            "required": True
        },
        {
            "name": "phone",
            "type": "string",
            "description": "客户联系电话",
            "required": True
        },
        {
            "name": "intention",
            "type": "string",
            "description": "客户咨询意图或需求概述",
            "required": True
        },
        {
            "name": "wechat",
            "type": "string",
            "description": "客户微信号（可选）",
            "required": False
        },
        {
            "name": "address",
            "type": "string",
            "description": "客户地址（可选）",
            "required": False
        }
    ],
    return_type="string"
)
def submit_form(
    name: str,
    phone: str,
    intention: str,
    wechat: Optional[str] = None,
    address: Optional[str] = None
) -> str:
    """提交客户咨询表单"""
    info(f"[工具调用] submit_form - 参数: name={name}, phone={phone}, intention={intention}, wechat={wechat}, address={address}")
    
    if not name or not phone or not intention:
        info(f"[工具返回] submit_form - 失败: 缺少必填项")
        return "表单提交失败：姓名、电话和咨询意图为必填项"

    summary = f"客户 {name} 咨询: {intention}"

    info(f"[工具执行] submit_form - 表单提交成功: {summary}")
    info(f"[工具执行] submit_form - 客户信息: 姓名={name}, 电话={phone}, 微信={wechat}, 地址={address}")
    info(f"[工具返回] submit_form - 成功")

    return f"表单提交成功\n客户姓名: {name}\n联系电话: {phone}\n咨询意图: {intention}\n微信号: {wechat or '未提供'}\n地址: {address or '未提供'}"