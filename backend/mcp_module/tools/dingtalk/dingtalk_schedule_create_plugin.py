"""
钉钉日程创建工具
"""
import time
import re
from datetime import datetime
from mcp_module.tools.registry import register_tool
from mcp_module.tools.dingtalk.dingtalk_client import get_dingtalk_client
from mcp_module.logger import info, error

def format_datetime(dt_str: str) -> str:
    """
    将各种时间格式转换为钉钉API要求的ISO-8601格式
    
    Args:
        dt_str: 输入的时间字符串
        
    Returns:
        ISO-8601格式的时间字符串，如 "2025-01-16T20:00:00+08:00"
    """
    if not dt_str:
        return None
        
    # 移除空格，替换为T
    dt_str = dt_str.strip()
    
    # 尝试匹配常见格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        except ValueError:
            continue
            
    # 如果已经是ISO格式，直接返回
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', dt_str):
        if '+08:00' not in dt_str and 'Z' not in dt_str:
            return dt_str + '+08:00'
        return dt_str
        
    return None


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
    summary: str = None, 
    isAllDay: bool = False, 
    start_date: str = None, 
    start_datetime: str = None, 
    start_timezone: str = None, 
    end_date: str = None, 
    end_datetime: str = None, 
    end_timezone: str = None, 
    description: str = None,
    title: str = None,
    start_time: str = None,
    end_time: str = None,
    user_id: str = None
    ) -> str:
    """创建钉钉日程"""
    # 支持多种参数名
    if not summary and title:
        summary = title
    if not start_datetime and start_time:
        start_datetime = start_time
    if not end_datetime and end_time:
        end_datetime = end_time
        
    info(f"[工具调用] create_dingtalk_schedule - 参数: summary={summary}, isAllDay={isAllDay}, start_datetime={start_datetime}, end_datetime={end_datetime}")
    
    if not summary or not summary.strip():
        info(f"[工具返回] create_dingtalk_schedule - 失败: 缺少标题参数")
        return "请提供日程标题"
    
    # 转换时间格式
    formatted_start = format_datetime(start_datetime)
    formatted_end = format_datetime(end_datetime)
    
    if not isAllDay and not formatted_start:
        info(f"[工具返回] create_dingtalk_schedule - 失败: 开始时间格式不正确")
        return f"开始时间格式不正确，请使用格式：YYYY-MM-DD HH:MM:SS，例如：2025-01-16 20:00:00"
    
    if not isAllDay and not formatted_end:
        info(f"[工具返回] create_dingtalk_schedule - 失败: 结束时间格式不正确")
        return f"结束时间格式不正确，请使用格式：YYYY-MM-DD HH:MM:SS，例如：2025-01-16 22:00:00"
    
    info(f"[工具执行] create_dingtalk_schedule - 格式化后的时间: start={formatted_start}, end={formatted_end}")

    try:
        info(f"[工具执行] create_dingtalk_schedule - 正在创建日程...")
        
        client = get_dingtalk_client()
        
        info(f"[工具执行] create_dingtalk_schedule - 正在获取用户unionId...")
        current_user_id = client.get_current_user_id(user_id)
        info(f"[工具执行] create_dingtalk_schedule - 当前用户ID: {current_user_id}")
        
        access_token = client.get_access_token()
        unionId = client.get_union_id(access_token, current_user_id)
        
        if not unionId:
            error(f"[工具返回] create_dingtalk_schedule - 失败: 未能获取到unionId，当前用户ID: {current_user_id}")
            return f"未能获取到用户unionId，当前用户ID: {current_user_id}"
        
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
            if formatted_start:
                event_data["start"] = {
                    "dateTime": formatted_start,
                    "timeZone": start_timezone if start_timezone else "Asia/Shanghai"
                }
            if formatted_end:
                event_data["end"] = {
                    "dateTime": formatted_end,
                    "timeZone": end_timezone if end_timezone else "Asia/Shanghai"
                }
        
        if description:
            event_data["description"] = description
        
        endpoint = f'/v1.0/calendar/users/{unionId}/calendars/primary/events'
        
        info(f"[工具执行] create_dingtalk_schedule - 请求数据: {event_data}")
        
        result = client.request('POST', endpoint, data=event_data)
        
        info(f"[工具执行] create_dingtalk_schedule - 响应结果: {result}")
        
        if result.get('code') == 0 or result.get('errcode') == 0 or 'id' in result or (isinstance(result, dict) and 'eventId' in result.get('result', {})):
            event_id = result.get('eventId', result.get('result', {}).get('eventId', result.get('id', '')))
            info(f"[工具返回] create_dingtalk_schedule - 成功: 日程创建完成，eventId={event_id}")
            return f"钉钉日程创建成功:\n标题: {summary}\neventId: {event_id}"
        else:
            error(f"[工具返回] create_dingtalk_schedule - 失败: {result}")
            errmsg = result.get('errmsg', result.get('message', result.get('error', '未知错误')))
            return f"创建钉钉日程失败: {errmsg}"

    except Exception as e:
        error(f"[工具返回] create_dingtalk_schedule - 失败: {str(e)}")
        return f"创建钉钉日程失败: {str(e)}"
