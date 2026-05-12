"""
钉钉日程删除工具
"""
from mcp_module.tools.registry import register_tool
from mcp_module.tools.dingtalk.dingtalk_client import get_dingtalk_client
from mcp_module.logger import info, error


@register_tool(
    name="delete_dingtalk_schedule",
    description="删除钉钉日程",
    parameters=[
        {
            "name": "eventId",
            "type": "string",
            "description": "日程ID",
            "required": True
        }
    ],
    return_type="string"
)
def delete_dingtalk_schedule(eventId: str) -> str:
    """删除钉钉日程"""
    info(f"[工具调用] delete_dingtalk_schedule - 参数: eventId={eventId}")
    
    if not eventId or not eventId.strip():
        info(f"[工具返回] delete_dingtalk_schedule - 失败: 缺少日程ID参数")
        return "请提供日程ID"

    try:
        info(f"[工具执行] delete_dingtalk_schedule - 正在删除日程...")
        
        client = get_dingtalk_client()
        
        delete_data = {
            "eventId": eventId
        }
        
        result = client.request('POST', '/topapi/calendar/event/delete', data=delete_data)
        
        if result.get('errcode') == 0:
            info(f"[工具返回] delete_dingtalk_schedule - 成功: 日程删除完成")
            return f"钉钉日程删除成功:\neventId: {eventId}"
        else:
            error(f"[工具返回] delete_dingtalk_schedule - 失败: {result}")
            return f"删除钉钉日程失败: {result.get('errmsg', '未知错误')}"

    except Exception as e:
        error(f"[工具返回] delete_dingtalk_schedule - 失败: {str(e)}")
        return f"删除钉钉日程失败: {str(e)}"


@register_tool(
    name="delete_dingtalk_schedule_by_id",
    description="通过ID删除钉钉日程",
    parameters=[
        {
            "name": "eventId",
            "type": "string",
            "description": "日程ID",
            "required": True
        }
    ],
    return_type="string"
)
def delete_dingtalk_schedule_by_id(eventId: str) -> str:
    """通过ID删除钉钉日程"""
    info(f"[工具调用] delete_dingtalk_schedule_by_id - 参数: eventId={eventId}")
    
    if not eventId or not eventId.strip():
        info(f"[工具返回] delete_dingtalk_schedule_by_id - 失败: 缺少日程ID参数")
        return "请提供日程ID"

    try:
        info(f"[工具执行] delete_dingtalk_schedule_by_id - 正在通过ID删除日程...")
        
        client = get_dingtalk_client()
        
        delete_data = {
            "eventId": eventId
        }
        
        result = client.request('POST', '/topapi/calendar/event/delete', data=delete_data)
        
        if result.get('errcode') == 0:
            info(f"[工具返回] delete_dingtalk_schedule_by_id - 成功: 日程删除完成")
            return f"钉钉日程删除成功:\neventId: {eventId}"
        else:
            error(f"[工具返回] delete_dingtalk_schedule_by_id - 失败: {result}")
            return f"通过ID删除钉钉日程失败: {result.get('errmsg', '未知错误')}"

    except Exception as e:
        error(f"[工具返回] delete_dingtalk_schedule_by_id - 失败: {str(e)}")
        return f"通过ID删除钉钉日程失败: {str(e)}"
