"""
天气预报推荐工具插件
"""

import random
from mcp_module.tools.registry import register_tool
from mcp_module.logger import info


weather_map = {
    "晴": {
        "reason": "晴天适合户外活动，推荐自然风光和户外景点",
        "types": ["风景名胜", "公园", "古镇", "湖边", "爬山步道"]
    },
    "多云": {
        "reason": "多云天气舒适，适合逛公园和城市地标",
        "types": ["公园", "城市地标", "特色街区", "植物园"]
    },
    "小雨": {
        "reason": "雨天适合室内活动，推荐博物馆和展馆",
        "types": ["博物馆", "美术馆", "科技馆", "室内乐园", "书店"]
    },
    "大雨": {
        "reason": "大雨天推荐室内场馆和商圈",
        "types": ["大型商场", "室内乐园", "温泉馆", "电影院"]
    },
    "高温": {
        "reason": "高温天气推荐避暑和室内空调景点",
        "types": ["水上乐园", "溶洞", "博物馆", "空调商场"]
    }
}

spots_db = {
    "风景名胜": ["黄山风景区", "张家界国家森林公园", "九寨沟景区", "峨眉山风景区"],
    "公园": ["杭州西湖公园", "北京颐和园", "上海世纪公园", "成都人民公园"],
    "古镇": ["乌镇古镇", "周庄古镇", "丽江古城", "凤凰古城", "南浔古镇"],
    "湖边": ["西湖", "洞庭湖", "洱海", "青海湖", "太湖"],
    "爬山步道": ["泰山", "华山", "黄山光明顶", "庐山", "武夷山"],
    "城市地标": ["北京故宫", "上海外滩", "广州塔", "深圳世界之窗", "成都宽窄巷子"],
    "特色街区": ["成都锦里", "南京夫子庙", "武汉户部巷", "重庆磁器口"],
    "植物园": ["北京植物园", "上海植物园", "厦门园林植物园", "昆明植物园"],
    "博物馆": ["国家博物馆", "故宫博物院", "陕西历史博物馆", "南京博物院"],
    "美术馆": ["中国美术馆", "上海美术馆", "广东美术馆", "四川美术馆"],
    "科技馆": ["中国科技馆", "上海科技馆", "广东科学中心", "深圳科学馆"],
    "室内乐园": ["万达乐园", "融创乐园", "乐高探索中心", "反弹蹦床公园"],
    "书店": ["方所书店", "钟书阁", "西西弗书店", "猫的天空之城"],
    "大型商场": ["万达广场", "万象城", "太古汇", "IFS国金中心"],
    "温泉馆": ["温泉度假村", "海底温泉", "日式温泉馆", "矿物温泉中心"],
    "电影院": ["万达影城", "CGV影城", "百丽宫影城", "IMAX影院"],
    "水上乐园": ["玛雅海滩水公园", "长隆水上乐园", "水上世界", "欢乐谷玛雅水寨"],
    "溶洞": ["黄龙洞", "银子岩", "芙蓉洞", "织金洞", "石林"]
}


@register_tool(
    name="get_weather_recommendation",
    description="根据天气情况推荐适合游玩的地点",
    parameters=[
        {
            "name": "city",
            "type": "string",
            "description": "要推荐的城市名称",
            "required": True
        },
        {
            "name": "weather",
            "type": "string",
            "description": "天气状况，可选值: 晴、多云、小雨、大雨、高温",
            "required": True
        },
        {
            "name": "temperature",
            "type": "integer",
            "description": "当前温度（摄氏度）",
            "required": False
        }
    ],
    return_type="string"
)
def get_weather_recommendation(city: str, weather: str, temperature: int = None) -> str:
    """根据天气情况推荐适合游玩的地点"""
    info(f"[工具调用] get_weather_recommendation - 参数: city={city}, weather={weather}, temperature={temperature}")

    if not city or not city.strip():
        info(f"[工具返回] get_weather_recommendation - 失败: 缺少城市参数")
        return "请提供要推荐的城市名称"

    if not weather or not weather.strip():
        info(f"[工具返回] get_weather_recommendation - 失败: 缺少天气参数")
        return "请提供当前天气状况"

    city = city.strip()
    weather = weather.strip()

    if weather == "高温" and temperature is not None and temperature < 35:
        weather = "晴"

    weather_info = weather_map.get(weather)
    if not weather_info:
        available_weathers = ", ".join(weather_map.keys())
        info(f"[工具返回] get_weather_recommendation - 失败: 不支持的天气类型")
        return f"不支持的天气类型，可选值: {available_weathers}"

    reason = weather_info["reason"]
    types = weather_info["types"]

    selected_types = random.sample(types, min(2, len(types)))
    recommendations = []

    for spot_type in selected_types:
        spots = spots_db.get(spot_type, [])
        if spots:
            selected_spot = random.choice(spots)
            recommendations.append(f"• {selected_spot} ({spot_type})")

    temp_info = f"，当前温度{temperature}°C" if temperature is not None else ""

    result = f"{city} {weather}{temp_info} 游玩推荐：\n\n"
    result += f"推荐理由：{reason}\n\n"
    result += "推荐景点：\n"
    result += "\n".join(recommendations)

    info(f"[工具返回] get_weather_recommendation - 成功: 生成{len(recommendations)}条推荐")
    return result