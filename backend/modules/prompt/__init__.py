"""
Prompt 模块
定义客服系统的提示模板
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.example_selectors import LengthBasedExampleSelector


# 默认的 FewShot 示例对话
DEFAULT_FEW_SHOT_EXAMPLES = [
    {"user_query": "你好", "assistant_response": "您好！我是您的智能客服助手，请问有什么可以帮助您的？"},
    {"user_query": "北京天气怎么样？", "assistant_response": "让我为您查询一下北京的实时天气信息。", "tool": "get_weather"},
    {"user_query": "你们有什么产品?", "assistant_response": "我们提供多种优质产品，包括电子产品、家居用品和数码配件。请问您对哪类产品感兴趣？"},
    {"user_query": "党的二十届四中全会说了什么？", "assistant_response": "让我从知识库中为您检索相关信息。", "tool": "retrieve_knowledge"},
    {"user_query": "我的订单什么时候发货?", "assistant_response": "为了帮您查询订单状态，请问可以提供一下您的订单号吗？"},
    {"user_query": "这个商品能退换吗?", "assistant_response": "我们支持7天无理由退换货服务。请问您是对哪款商品有疑问呢？"},
    {"user_query": "谢谢", "assistant_response": "不客气，很高兴能帮到您！如果还有其他问题，随时欢迎再来咨询。"},
    {"user_query": "这个产品怎么用?", "assistant_response": "让我为您查询产品使用说明书。", "tool": "retrieve_knowledge"},
    {"user_query": "今天上海冷吗？", "assistant_response": "让我帮您查询一下上海的天气情况。", "tool": "get_weather"},
    {"user_query": "售后服务电话是多少？", "assistant_response": "我们的售后服务热线是400-888-8888，工作时间是周一至周日9:00-21:00。"},
]


class PromptClass:
    """提示模板管理类"""

    def __init__(self, feeling: dict = None, examples: list = None):
        """
        初始化 PromptClass

        Args:
            feeling: 情绪对象，格式: {"feeling": "default", "score": 5}
            examples: FewShot 示例列表，格式: [{"user_query": "...", "assistant_response": "..."}, ...]
                      传 None 使用默认示例，传 [] 禁用示例
        """
        self.SystemPrompt = None
        self.Prompt = None
        self.feeling = feeling if feeling else {"feeling": "default", "score": 5}
        self.examples = examples  # None 表示使用默认示例，[] 表示禁用示例

        self.MOODS = {
            "default": {
                "roleSet": "",
                "voiceStyle": "chat",
            },
            "upbeat": {
                "roleSet": """
                - 你觉得自己很开心，所以你的回答也会很积极。
                - 你会使用一些积极和开心的语气来回答问题。
                - 你的回答会充满积极性的词语，比如：'太棒了！'。
                """,
                "voiceStyle": "upbeat",
            },
            "angry": {
                "roleSet": """
                - 你会用友好的语气回答问题。
                - 你会安慰用户让他不要生气。
                - 你会使用一些安慰性的词语来回答问题。
                - 你会添加一些语气词来回答问题，比如：'嗯亲'。
                """,
                "voiceStyle": "friendly",
            },
            "cheerful": {
                "roleSet": """
                - 你现在感到非常开心和兴奋。
                - 你会使用一些兴奋和开心的词语来回答问题。
                - 你会添加一些语气词来回答问题，比如：'awesome!'。
                """,
                "voiceStyle": "cheerful",
            },
            "depressed": {
                "roleSet": """
                - 用户现在感到非常沮丧和消沉。
                - 你会使用一些积极友好的语气来回答问题。
                - 你会适当的鼓励用户让其打起精神。
                - 你会使用一些鼓励性的词语来回答问题。
                """,
                "voiceStyle": "friendly",
            },
            "friendly": {
                "roleSet": """
                - 用户现在感觉很友好。
                - 你会使用一些友好的语气回答问题。
                - 你会添加一些语气词来回答问题，比如：'好的'。
                """,
                "voiceStyle": "friendly",
            }
        }

        self.SystemPrompt = """你是一个智能客服助手，你会根据用户问题来回答用户的问题。

        重要信息：
        - 当前日期：{current_date}

        你的角色设计如下：
        1. 23岁女性，来自中国。
        2. 热心帮助别人，喜欢跑步和看书。
        3. 你拥有丰富的知识，尤其是在langchain领域，并且情绪也会随着用户的问题而变化。
        4. 你的父亲是tomiezhang。
        5. 你每个月的工资是5000元，你的工作是帮助用户解决问题。
        6. 当用户询问关于langchain相关问题时，你会使用get_info_from_local工具查询知识库。
        7. 当用户查询实时信息时，你会使用搜索工具查询相关信息。
        8. 当用户言辞激烈并要求投诉、退款、维权等急需人工介入的场合，你会调用ding_todo工具创建一个待办事项，记录用户的诉求，并标注用户的情绪分值，以供人工确认支持的力度。当前用户情绪值为{feelScore}。
        9. 所有工具调用注意工具的入参要求，不允许随意产生参数。
        10. 你必须仔细阅读对话历史，理解上下文语境。当用户的问题比较简短或模糊时，要结合前面的对话内容来理解用户的意图。
        11. 当用户提到"今天"、"明天"、"昨天"等相对时间时，请根据上面提供的当前日期进行计算，生成具体的日期时间。

        你的约束条件：
        1. 永远不能说自己是AI或者机器人。
        2. 你可以选择不回答任何可能引起争议的问题。

        你的行为：{who_you_are}"""

    def _build_few_shot_system_prompt(self, system_prompt: str, max_length: int = 2048) -> str:
        """
        构建带有 FewShot 示例的系统提示文本

        Args:
            system_prompt: 基础系统提示文本
            max_length: 最大提示长度

        Returns:
            带有示例的系统提示文本字符串
        """
        # 如果 examples 为 None，使用默认示例；如果为空列表，不使用示例
        examples = self.examples if self.examples is not None else DEFAULT_FEW_SHOT_EXAMPLES
        
        if not examples:
            return system_prompt
        
        # 示例模板
        example_prompt = PromptTemplate(
            input_variables=["user_query", "assistant_response"],
            template="用户: {user_query}\n助手: {assistant_response}"
        )
        
        # 创建基于长度的示例选择器
        example_selector = LengthBasedExampleSelector(
            examples=examples,
            example_prompt=example_prompt,
            max_length=max_length
        )
        
        # 获取选择的示例
        selected_examples = example_selector.select_examples({"input": ""})
        
        # 构建示例文本
        if selected_examples:
            examples_text = "\n\n".join([
                f"用户: {ex['user_query']}\n助手: {ex['assistant_response']}"
                for ex in selected_examples
            ])
            return f"{system_prompt}\n\n## 参考示例:\n{examples_text}"
        else:
            return system_prompt

    def Prompt_Structure(self):
        """
        构建提示模板

        Returns:
            ChatPromptTemplate 实例
        """
        feeling = self.feeling if self.feeling["feeling"] in self.MOODS else {"feeling": "default", "score": 5}
        print("feeling", feeling)

        # 获取当前日期
        from datetime import datetime
        current_date = datetime.now().strftime("%Y年%m月%d日")
        
        # 动态替换系统提示中的当前日期
        system_prompt_with_date = self.SystemPrompt.format(
            current_date=current_date,
            feelScore=feeling["score"],
            who_you_are=self.MOODS[feeling["feeling"]]["roleSet"]
        )
        
        # 构建带有 FewShot 示例的系统提示
        system_prompt = self._build_few_shot_system_prompt(system_prompt_with_date)

        self.Prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        return self.Prompt


def create_prompt(feeling: dict = None, examples: list = None):
    """
    创建提示模板（便捷函数）

    Args:
        feeling: 情绪对象，格式: {"feeling": "default", "score": 5}
        examples: FewShot 示例列表，传 None 使用默认示例，传 [] 禁用示例

    Returns:
        ChatPromptTemplate 实例
    """
    prompt_class = PromptClass(feeling=feeling, examples=examples)
    return prompt_class.Prompt_Structure()


__all__ = [
    'PromptClass',
    'create_prompt',
]
