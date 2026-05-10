"""
智能客服 Agent 主应用
Flask Web 服务入口
LangGraph 版本
"""

import uuid
import sys
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from modules.ai_client import AIClient
from modules.langgraph import LangGraphAgent, RAGWorkflow
from modules.checkpoint import MemorySaver
from modules.assistant import Agent as LangChainAgent
from modules.prompt import create_few_shot_prompt
from modules.rate_limit import RateLimiter
from mcp_module import MCPToolService

if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
if sys.stderr.encoding != 'utf-8':
    import codecs
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ['PYTHONIOENCODING'] = 'utf-8'

load_dotenv()

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
CORS(app)

rate_limiter = RateLimiter()
rate_limiter.init_app(app)

assistant_instance = None
sessions = {}


def init_system():
    """初始化系统组件"""
    global assistant_instance

    print("=" * 50)
    print("智能客服系统启动中... (LangGraph 版本)")
    print("=" * 50)

    print("\n[1/4] 初始化 AI 客户端...")
    try:
        ai_client = AIClient()
        print("AI 客户端初始化完成")
    except Exception as e:
        print("AI 客户端初始化失败: {}".format(e))
        raise

    print("\n[2/4] 初始化 RAG 工作流...")
    try:
        rag_workflow = RAGWorkflow(llm_client=ai_client)
        rag_workflow.build_index()
        print("RAG 工作流初始化完成")
    except Exception as e:
        print("RAG 工作流初始化警告: {}".format(e))
        rag_workflow = None

    print("\n[3/4] 初始化 LangChain Agent...")
    try:
        tools = MCPToolService.get_tools()

        langchain_agent = LangChainAgent(options={
            "prompt": create_few_shot_prompt(),
            "tools": tools,
            "aiClient": ai_client
        })
        print("LangChain Agent 初始化完成")
    except Exception as e:
        print("LangChain Agent 初始化失败: {}".format(e))
        langchain_agent = None

    print("\n[4/4] 初始化 LangGraph 调度层...")
    try:
        # 根据配置选择 checkpointer
        # 生产环境可以替换为 RedisSaver 或其他持久化方案
        checkpointer = MemorySaver()
        
        assistant_instance = LangGraphAgent(
            agent=langchain_agent,
            rag_workflow=rag_workflow,
            checkpointer=checkpointer
        )
        print("LangGraph 调度层初始化完成")
    except Exception as e:
        print("LangGraph 调度层初始化失败: {}".format(e))
        raise

    print("\n" + "=" * 50)
    print("智能客服系统就绪!")
    print("=" * 50)
    print("\n服务地址: http://localhost:5000")
    print("API 文档:")
    print("  GET  /start  - 检查服务状态")
    print("  POST /chat   - 发送对话请求")
    print("=" * 50 + "\n")


@app.route('/start', methods=['GET'])
@rate_limiter.limit("start_limit")
def start():
    """检查服务状态"""
    try:
        status = {
            "status": "ready",
            "message": "客服系统已就绪 (LangGraph 版本)",
            "model": "qwen3.6-flash"
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/chat', methods=['POST'])
@rate_limiter.limit("chat_limit")
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

        result = assistant_instance.invoke(user_message, session_id)

        response = {
            "reply": result.get("answer", ""),
            "tool_calls": [],
            "session_id": session_id,
            "finished": False
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


if __name__ == '__main__':
    init_system()
    app.run(host='0.0.0.0', port=5000, debug=True)
