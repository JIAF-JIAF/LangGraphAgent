"""
钉钉 Stream 客户端服务
用于接收和响应钉钉机器人消息
"""

import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.factory import AssistantFactory
from modules.logger import log, exception
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

user_sessions = {}
processed_messages = set()  # 用于消息去重


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger('dingtalk_stream')


def get_session_id(uid):
    """根据 uid 获取或创建会话 ID"""
    if uid not in user_sessions:
        user_sessions[uid] = uid
    return user_sessions[uid]


class DingTalkChatbotHandler(ChatbotHandler):
    """钉钉机器人消息处理器"""

    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant

    async def process(self, callback):
        """处理钉钉消息回调"""
        try:
            # 打印完整的回调消息
            log("钉钉回调消息", "DingTalk")
            log(f"callback.data: {callback.data}", "DingTalk")
            log("========================", "DingTalk")

            message = ChatbotMessage.from_dict(callback.data)

            # 打印 message 对象的所有属性
            log(f"message.sender_id: {message.sender_id}", "DingTalk")
            log(f"message.sender_staff_id: {getattr(message, 'sender_staff_id', 'N/A')}", "DingTalk")
            log(f"message.sender_nick: {getattr(message, 'sender_nick', 'N/A')}", "DingTalk")

            # 获取消息 ID（唯一标识）
            msg_id = message.message_id
            log(f"消息ID(msgId): {msg_id}", "DingTalk")

            # 去重检查 - 如果已处理过，直接返回
            if msg_id in processed_messages:
                log(f"消息已处理，跳过: {msg_id}", "DingTalk")
                return AckMessage.STATUS_OK, 'OK'

            # 获取用户 ID - 使用 senderStaffId
            uid = getattr(message, 'sender_staff_id', message.sender_id)
            log(f"用户ID(senderStaffId): {uid}", "DingTalk")

            # 获取消息内容
            user_message = message.text.content
            log(f"消息内容: {user_message}", "DingTalk")

            # 获取会话 ID
            session_id = get_session_id(uid)

            # 调用模型生成回复（传递 uid）
            result = self.assistant.invoke(user_message, session_id, uid=uid)
            reply = result.get("answer", "")

            log(f"回复内容: {reply}", "DingTalk")

            # 发送回复
            self.reply_text(reply, message)

            # 记录已处理的消息 ID
            processed_messages.add(msg_id)
            log(f"消息已记录: {msg_id}", "DingTalk")

            # 清理旧的消息 ID（防止内存泄漏，保留最近1000条）
            if len(processed_messages) > 1000:
                old_count = len(processed_messages) - 1000
                old_list = list(processed_messages)[:old_count]
                for old_id in old_list:
                    processed_messages.remove(old_id)
                log(f"清理旧消息ID: 移除 {old_count} 条", "DingTalk")

            # 返回成功状态
            return AckMessage.STATUS_OK, 'OK'

        except Exception as e:
            exception(f"处理异常: {e}", "DingTalk", e)
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

        assistant, _ = AssistantFactory.create_assistant()
        client.register_callback_handler(ChatbotMessage.TOPIC, DingTalkChatbotHandler(assistant))
        logger.info("已注册ChatbotMessage的回调处理器")

        # 启动客户端
        logger.info("正在启动钉钉客户端...")
        client.start_forever()

    except Exception as e:
        logger.error(f"连接钉钉时出错: {e}", exc_info=True)


if __name__ == '__main__':
    main()
