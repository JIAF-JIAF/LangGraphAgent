"""
钉钉 Stream 客户端服务
用于接收和响应钉钉机器人消息
"""

import os
import sys
import json
import logging
from dotenv import load_dotenv

# 添加模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.ai_client import AIClient
from modules.langgraph import LangGraphAgent, RAGWorkflow
from modules.checkpoint import CheckpointFactory
from modules.assistant import Agent as LangChainAgent
from modules.prompt import create_prompt
from modules.feeling import FeelingDetector
from mcp_module import MCPToolService
from dingtalk_stream import ChatbotHandler, ChatbotMessage, Credential, DingTalkStreamClient, AckMessage

# 确保输出编码正确
if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
if sys.stderr.encoding != 'utf-8':
    import codecs
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ['PYTHONIOENCODING'] = 'utf-8'

load_dotenv()

# 全局变量
assistant_instance = None
user_sessions = {}


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger('dingtalk_stream')


def init_system():
    """初始化系统组件"""
    global assistant_instance

    print("=" * 50)
    print("钉钉 Stream 服务启动中...")
    print("=" * 50)

    print("\n[1/5] 初始化 AI 客户端...")
    try:
        ai_client = AIClient()
        print("AI 客户端初始化完成")
    except Exception as e:
        print("AI 客户端初始化失败: {}".format(e))
        raise

    print("\n[2/5] 初始化感情侦测器...")
    try:
        feeling_detector = FeelingDetector(llm_client=ai_client)
        print("感情侦测器初始化完成")
    except Exception as e:
        print("感情侦测器初始化失败: {}".format(e))
        feeling_detector = None

    print("\n[3/5] 初始化 RAG 工作流...")
    try:
        rag_workflow = RAGWorkflow(llm_client=ai_client)
        rag_workflow.build_index()
        print("RAG 工作流初始化完成")
    except Exception as e:
        print("RAG 工作流初始化警告: {}".format(e))
        rag_workflow = None

    print("\n[4/5] 初始化 LangChain Agent...")
    try:
        tools = MCPToolService.get_tools()

        langchain_agent = LangChainAgent(options={
            "prompt": create_prompt(feeling={"feeling": "default", "score": 5}),
            "tools": tools,
            "aiClient": ai_client
        })
        print("LangChain Agent 初始化完成")
    except Exception as e:
        print("LangChain Agent 初始化失败: {}".format(e))
        langchain_agent = None

    print("\n[5/5] 初始化 LangGraph 调度层...")
    try:
        checkpoint_storage = os.getenv("CHECKPOINT_STORAGE", "memory").lower()
        print(f"  使用 {'Redis 持久化' if checkpoint_storage == 'redis' else '内存'}存储")

        checkpointer = CheckpointFactory.build(name=checkpoint_storage)

        assistant_instance = LangGraphAgent(
            agent=langchain_agent,
            rag_workflow=rag_workflow,
            checkpointer=checkpointer,
            feeling_detector=feeling_detector
        )
        print("LangGraph 调度层初始化完成")
    except Exception as e:
        print("LangGraph 调度层初始化失败: {}".format(e))
        raise

    print("\n" + "=" * 50)
    print("钉钉 Stream 服务就绪!")
    print("=" * 50 + "\n")


def get_session_id(uid):
    """根据 uid 获取或创建会话 ID"""
    if uid not in user_sessions:
        user_sessions[uid] = uid
    return user_sessions[uid]


class DingTalkChatbotHandler(ChatbotHandler):
    """钉钉机器人消息处理器"""

    def __init__(self):
        super().__init__()

    async def process(self, callback):
        """处理钉钉消息回调"""
        try:
            # 打印完整的回调消息
            print(f"\n===== 钉钉回调消息 =====", flush=True)
            print(f"callback.data: {callback.data}", flush=True)
            print(f"callback.data类型: {type(callback.data)}", flush=True)
            import json
            try:
                print(f"callback.data(JSON): {json.dumps(callback.data, ensure_ascii=False, indent=2)}", flush=True)
            except:
                pass
            print(f"========================\n", flush=True)
            
            message = ChatbotMessage.from_dict(callback.data)
            
            # 打印 message 对象的所有属性
            print(f"message对象属性: {dir(message)}", flush=True)
            print(f"message.sender_id: {message.sender_id}", flush=True)
            print(f"message.sender_staff_id: {getattr(message, 'sender_staff_id', 'N/A')}", flush=True)
            print(f"message.sender_nick: {getattr(message, 'sender_nick', 'N/A')}", flush=True)
            
            # 获取用户 ID - 使用 senderStaffId
            uid = getattr(message, 'sender_staff_id', message.sender_id)
            print(f"\n[钉钉消息] 用户ID(senderStaffId): {uid}", flush=True)

            # 获取消息内容
            user_message = message.text.content
            print(f"[钉钉消息] 消息内容: {user_message}", flush=True)

            # 获取会话 ID
            session_id = get_session_id(uid)

            # 调用模型生成回复（传递 uid）
            result = assistant_instance.invoke(user_message, session_id, uid)
            reply = result.get("answer", "")

            print(f"[钉钉消息] 回复内容: {reply}", flush=True)

            # 发送回复
            self.reply_text(reply, message)
            
            # 返回成功状态
            return AckMessage.STATUS_OK, 'OK'

        except Exception as e:
            print(f"[钉钉消息] 处理异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return AckMessage.STATUS_OK, 'OK'


def main():
    """主函数"""
    logger = setup_logging()
    logger.info("启动钉钉流客户端")

    # 从环境变量中获取钉钉的 app key 和 app secret
    app_id = os.getenv("DINGTALK_CLIENT_ID")
    app_secret = os.getenv("DINGTALK_CLIENT_SECRET")
    
    logger.info(f"应用ID: {app_id}")
    logger.info("使用凭证连接钉钉")

    try:
        credential = Credential(app_id, app_secret)
        client = DingTalkStreamClient(credential, logger=logger)
        logger.info("钉钉客户端创建成功")

        # 注册回调处理器
        client.register_callback_handler(ChatbotMessage.TOPIC, DingTalkChatbotHandler())
        logger.info("已注册ChatbotMessage的回调处理器")

        # 启动客户端
        logger.info("正在启动钉钉客户端...")
        client.start_forever()

    except Exception as e:
        logger.error(f"连接钉钉时出错: {e}", exc_info=True)


if __name__ == '__main__':
    init_system()
    main()