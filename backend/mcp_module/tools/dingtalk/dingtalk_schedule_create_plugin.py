"""
钉钉日程创建工具
"""
import time
from mcp_module.tools.registry import register_tool
from mcp_module.tools.dingtalk.dingtalk_client import get_dingtalk_client
from mcp_module.logger import info, error


@register_tool(
    name="create_dingtalk_schedule",
    description="创建钉钉日程",
    parameters=[
        {
            "name": "summary",
            "type": "string",
            "description": "日程标题，最大不超过2048个字符",
            "required": True
        },
        {
            "name": "start_date",
            "type": "string",
            "description": "日程开始日期，格式:yyyy-MM-dd，当前时间为{}，说明(全天日程必须有值，非全天日程必须留空)".format(time.strftime("%Y-%m-%d", time.localtime())),
            "required": False
        },
        {
            "name": "start_datetime",
            "type": "string",
            "description": "日程开始时间，格式为ISO-8601的date-time格式，当前时间为{}，说明(全天日程必须留空，非全天日程必须有值)".format(time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())),
            "required": False
        },
        {
            "name": "start_timezone",
            "type": "string",
            "description": "日程开始时间所属时区，TZ database name格式，固定为Asia/Shanghai，说明(全天日程必须留空，非全天日程必须有值)",
            "required": False
        },
        {
            "name": "end_date",
            "type": "string",
            "description": "日程结束日期，格式:yyyy-MM-dd，当前时间为{}，说明(全天日程必须有值，非全天日程必须留空)".format(time.strftime("%Y-%m-%d", time.localtime())),
            "required": False
        },
        {
            "name": "end_datetime",
            "type": "string",
            "description": "日程结束时间，格式为ISO-8601的date-time格式，当前时间为{}，说明(全天日程必须留空，非全天日程必须有值)".format(time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())),
            "required": False
        },
        {
            "name": "end_timezone",
            "type": "string",
            "description": "日程结束时间所属时区，TZ database name格式，固定为Asia/Shanghai，说明(全天日程必须留空，非全天日程必须有值)",
            "required": False
        },
        {
            "name": "isAllDay",
            "type": "boolean",
            "description": "是否全天日程，true是false不是",
            "required": True
        },
        {
            "name": "description",
            "type": "string",
            "description": "日程描述，最大不超过5000个字符",
            "required": False
        }
    ],
    return_type="string"
)
def create_dingtalk_schedule(
    summary: str, 
    isAllDay: bool, 
    start_date: str = None, 
    start_datetime: str = None, 
    start_timezone: str = None, 
    end_date: str = None, 
    end_datetime: str = None, 
    end_timezone: str = None, 
    description: str = None
    ) -> str:
    """创建钉钉日程"""
    info(f"[工具调用] create_dingtalk_schedule - 参数: summary={summary}, isAllDay={isAllDay}")
    
    if not summary or not summary.strip():
        info(f"[工具返回] create_dingtalk_schedule - 失败: 缺少标题参数")
        return "请提供日程标题"

    try:
        info(f"[工具执行] create_dingtalk_schedule - 正在创建日程...")
        
        client = get_dingtalk_client()
        
        info(f"[工具执行] create_dingtalk_schedule - 正在获取用户unionId...")
        access_token = client.get_access_token()
        unionId = client.get_union_id(access_token, client.user_id)
        
        if not unionId:
            error(f"[工具返回] create_dingtalk_schedule - 失败: 未能获取到unionId")
            return "未能获取到用户unionId"
        
        info(f"[工具执行] create_dingtalk_schedule - 获取到unionId: {unionId}")
        
        event_data = {
            "summary": summary
        }
        
        if isAllDay:
            if start_date:
                event_data["start"] = {"date": start_date}
            if end_date:
                event_data["end"] = {"date": end_date}
        else:
            if start_datetime:
                event_data["start"] = {
                    "dateTime": start_datetime,
                    "timeZone": start_timezone if start_timezone else "Asia/Shanghai"
                }
            if end_datetime:
                event_data["end"] = {
                    "dateTime": end_datetime,
                    "timeZone": end_timezone if end_timezone else "Asia/Shanghai"
                }
        
        if description:
            event_data["description"] = description
        
        endpoint = f'/v1.0/calendar/users/{unionId}/calendars/primary/events'
        result = client.request('POST', endpoint, data=event_data)
        
        if result.get('code') == 0 or result.get('errcode') == 0 or 'id' in result:
            event_id = result.get('eventId', result.get('result', {}).get('eventId', result.get('id', '')))
            info(f"[工具返回] create_dingtalk_schedule - 成功: 日程创建完成，eventId={event_id}")
            return f"钉钉日程创建成功:\n标题: {summary}\neventId: {event_id}"
        else:
            error(f"[工具返回] create_dingtalk_schedule - 失败: {result}")
            errmsg = result.get('errmsg', result.get('message', '未知错误'))
            return f"创建钉钉日程失败: {errmsg}"

    except Exception as e:
        error(f"[工具返回] create_dingtalk_schedule - 失败: {str(e)}")
        return f"创建钉钉日程失败: {str(e)}"
