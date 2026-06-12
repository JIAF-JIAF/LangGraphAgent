"""
天气查询工具插件
"""

import requests
from mcp_server.tools.registry import register_tool
from mcp_server.logger import info


@register_tool(
    name="get_weather",
    description="查询指定城市的实时天气",
    parameters=[
        {
            "name": "city",
            "type": "string",
            "description": "要查询天气的城市名称，例如：杭州、北京、上海等",
            "required": True
        }
    ],
    return_type="string"
)
def get_weather(city: str) -> str:
    """查询指定城市的实时天气"""
    info(f"[工具调用] get_weather - 参数: city={city}")
    
    if not city or not city.strip():
        info(f"[工具返回] get_weather - 失败: 缺少城市参数")
        return "请提供要查询天气的城市名称"

    city = city.strip()

    try:
        info(f"[工具执行] get_weather - 正在查询 {city} 的天气...")
        url = f"https://wttr.in/{city}?format=j1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        weather_data = response.json()

        current = weather_data.get('current_condition', [{}])[0]
        location = weather_data.get('nearest_area', [{}])[0]

        city_name = location.get('areaName', [{}])[0].get('value', city)
        region = location.get('region', [{}])[0].get('value', '')
        country = location.get('country', [{}])[0].get('value', '')

        temp_c = current.get('temp_C', 'N/A')
        feels_like_c = current.get('FeelsLikeC', 'N/A')
        weather_desc = current.get('weatherDesc', [{}])[0].get('value', 'N/A')
        humidity = current.get('humidity', 'N/A')
        wind_speed = current.get('windspeedKmph', 'N/A')
        wind_dir = current.get('winddir16Point', 'N/A')
        uv_index = current.get('uvIndex', 'N/A')
        visibility = current.get('visibility', 'N/A')

        weather_report = f"{city_name} ({region}, {country}) 实时天气:\n"
        weather_report += f"温度: {temp_c}C (体感 {feels_like_c}C)\n"
        weather_report += f"天气: {weather_desc}\n"
        weather_report += f"湿度: {humidity}%\n"
        weather_report += f"风速: {wind_speed} km/h, 风向: {wind_dir}\n"
        weather_report += f"紫外线指数: {uv_index}\n"
        weather_report += f"能见度: {visibility} km"

        info(f"[工具返回] get_weather - 成功: {city_name} 天气查询完成")
        return weather_report

    except Exception as e:
        info(f"[工具返回] get_weather - 失败: {str(e)}")
        return f"查询天气失败: {str(e)}"