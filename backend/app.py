"""
智能客服 Agent 主应用
Flask Web 服务入口
LangGraph 版本
"""

import uuid
import sys
import os
from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from dotenv import load_dotenv

from modules.factory import AssistantFactory
from modules.rate_limit import RateLimiter

if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
if sys.stderr.encoding != 'utf-8':
    import codecs
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ['PYTHONIOENCODING'] = 'utf-8'

load_dotenv()


def create_app():
    """
    Flask Application Factory

    Returns:
        Flask 应用实例
    """
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
    CORS(app)

    rate_limiter = RateLimiter()
    rate_limiter.init_app(app)

    app.extensions['rate_limiter'] = rate_limiter
    app.extensions['sessions'] = {}
    app.extensions['assistant'] = None

    print("=" * 50)
    print("智能客服系统启动中... (LangGraph 版本)")
    print("=" * 50)

    assistant, _ = AssistantFactory.create_assistant()
    app.extensions['assistant'] = assistant

    print("\n" + "=" * 50)
    print("智能客服系统就绪!")
    print("=" * 50)
    print("\n服务地址: http://localhost:5000")
    print("API 文档:")
    print("  GET  /start  - 检查服务状态")
    print("  POST /chat   - 发送对话请求")
    print("=" * 50 + "\n")

    @app.route('/start', methods=['GET'])
    @app.extensions['rate_limiter'].limit("start_limit")
    def start():
        """检查服务状态"""
        try:
            status = {
                "status": "ready",
                "message": "客服系统已就绪 (LangGraph 版本)",
                "model": "qwen3.5-flash",
                "features": ["feeling_detection", "RAG", "tool_calling"]
            }
            return jsonify(status)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/chat', methods=['POST'])
    @app.extensions['rate_limiter'].limit("chat_limit")
    def chat():
        """处理对话请求"""
        try:
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "缺少 message 字段"}), 400

            user_message = data['message']
            session_id = data.get('session_id', str(uuid.uuid4()))

            print("\n[对话请求] Session: {}".format(session_id), flush=True)
            print("用户: {}".format(user_message), flush=True)

            assistant = app.extensions['assistant']
            result = assistant.invoke(user_message, session_id)

            response = {
                "reply": result.get("answer", ""),
                "tool_calls": [],
                "session_id": session_id,
                "finished": False,
                "feeling": result.get("feeling", {"feeling": "default", "score": 5})
            }

            return jsonify(response)

        except Exception as e:
            print("对话处理异常: {}".format(e))
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "error": "请求过于频繁，请稍后再试",
            "message": str(e.description)
        }), 429

    return app


app = create_app()


if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
