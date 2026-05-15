"""
钉钉日程查询工具
"""
import time
from mcp_module.tools.registry import register_tool
from mcp_module.tools.dingtalk.dingtalk_client import get_dingtalk_client
from mcp_module.logger import info, error


@register_tool(
    name="query_dingtalk_schedule",
    description="查询钉钉日程",
    parameters=[
        {
            "name": "timeMin",
            "type": "string",
            "description": "日程开始时间的最小值，格式为ISO-8601的date-time格式，如2020-01-01T10:15:30+08:00，当前时间为{}".format(time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())),
            "required": False
        },
        {
            "name": "timeMax",
            "type": "string",
            "description": "日程开始时间的最大值，格式为ISO-8601的date-time格式，如2020-01-01T10:15:30+08:00，当前时间为{}".format(time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())),
            "required": False
        },
        {
            "name": "showDeleted",
            "type": "boolean",
            "description": "是否返回已删除的日程，true返回，false(默认)不返回",
            "required": False
        },
        {
            "name": "maxResults",
            "type": "integer",
            "description": "最大返回记录数，最大值100，默认值100",
            "required": False
        },
        {
            "name": "maxAttendees",
            "type": "integer",
            "description": "每个日程的参与者查询个数，默认100，最大100",
            "required": False
        },
        {
            "name": "nextToken",
            "type": "string",
            "description": "分页游标，用于翻页查询",
            "required": False
        },
        {
            "name": "syncToken",
            "type": "string",
            "description": "增量同步token",
            "required": False
        },
        {
            "name": "user_id",
            "type": "string",
            "description": "用户ID，内部参数",
            "required": False
        }
    ],
    return_type="string"
)
def query_dingtalk_schedule(
    timeMin: str = None, 
    timeMax: str = None, 
    showDeleted: bool = None, 
    maxResults: int = None, 
    maxAttendees: int = None, 
    nextToken: str = None, 
    syncToken: str = None,
    user_id: str = None
    ) -> str:
    """查询钉钉日程"""
    info(f"[工具调用] query_dingtalk_schedule - 参数: timeMin={timeMin}, timeMax={timeMax}, showDeleted={showDeleted}, maxResults={maxResults}, maxAttendees={maxAttendees}, nextToken={nextToken}, syncToken={syncToken}")

    try:
        info(f"[工具执行] query_dingtalk_schedule - 正在查询日程...")
        
        client = get_dingtalk_client()
        
        info(f"[工具执行] query_dingtalk_schedule - 正在获取用户unionId...")
        access_token = client.get_access_token()
        unionId = client.get_union_id(access_token, client.get_current_user_id(user_id))
        
        if not unionId:
            error(f"[工具返回] query_dingtalk_schedule - 失败: 未能获取到unionId")
            return "未能获取到用户unionId"
        
        info(f"[工具执行] query_dingtalk_schedule - 获取到unionId: {unionId}")
        
        params = {}
        if timeMin:
            params['timeMin'] = timeMin
        if timeMax:
            params['timeMax'] = timeMax
        if showDeleted is not None:
            params['showDeleted'] = showDeleted
        if maxResults:
            params['maxResults'] = maxResults
        if maxAttendees:
            params['maxAttendees'] = maxAttendees
        if nextToken:
            params['nextToken'] = nextToken
        if syncToken:
            params['syncToken'] = syncToken
        
        endpoint = f'/v1.0/calendar/users/{unionId}/calendars/primary/events'
        result = client.request('GET', endpoint, params=params)
        
        if result.get('code') == 0 or result.get('errcode') == 0 or 'events' in result:
            events = result.get('events', [])
            next_token = result.get('nextToken', '')
            sync_token = result.get('syncToken', '')
            
            info(f"[工具返回] query_dingtalk_schedule - 成功: 查询到 {len(events)} 个日程")
            
            result_str = f"钉钉日程查询成功:\n共找到 {len(events)} 个日程:\n"
            for i, event in enumerate(events, 1):
                result_str += f"\n{i}. {event.get('summary', '无标题')}"
                
                start_info = event.get('start', {})
                if start_info.get('dateTime'):
                    result_str += f"\n   开始时间: {start_info['dateTime']}"
                elif start_info.get('date'):
                    result_str += f"\n   开始日期: {start_info['date']}"
                
                end_info = event.get('end', {})
                if end_info.get('dateTime'):
                    result_str += f"\n   结束时间: {end_info['dateTime']}"
                elif end_info.get('date'):
                    result_str += f"\n   结束日期: {end_info['date']}"
                
                if event.get('isAllDay'):
                    result_str += f"\n   全天日程: {'是' if event['isAllDay'] else '否'}"
                
                if event.get('id'):
                    result_str += f"\n   日程ID: {event['id']}"
                
                if event.get('description'):
                    result_str += f"\n   描述: {event['description']}"
            
            tokens = {k: v for k, v in [("nextToken", next_token), ("syncToken", sync_token)] if v}
            if tokens:
                result_str += "\n\n" + "\n".join(f"{k}: {v}" for k, v in tokens.items())
            
            return result_str
        else:
            error(f"[工具返回] query_dingtalk_schedule - 失败: {result}")
            errmsg = result.get('errmsg', result.get('message', '未知错误'))
            return f"查询钉钉日程失败: {errmsg}"

    except Exception as e:
        error(f"[工具返回] query_dingtalk_schedule - 失败: {str(e)}")
        return f"查询钉钉日程失败: {str(e)}"
