"""
智能客服 Agent 主应用
Flask Web 服务入口
LangGraph 版本
"""

import uuid
import sys
import os
import shutil
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from modules.ai_client import AIClient
from modules.langgraph import LangGraphAgent, TaskPlanner, ReflectionChecker
from modules.rag import RAGWorkflow
from modules.checkpoint import CheckpointFactory
from modules.assistant import Agent as LangChainAgent
from modules.prompt import create_prompt
from modules.feeling import FeelingDetector
from modules.rate_limit import RateLimiter
from modules.skill import get_engine, SkillManagerAdapter
from mcp_module import MCPToolService
from modules.rag.indexer import ChromaIndexer

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

        task_planner = TaskPlanner(llm_client=ai_client)
        print("  任务规划器初始化完成")

        reflection_checker = ReflectionChecker(llm_client=ai_client)
        print("  反思校验器初始化完成")

        skill_engine = get_engine()
        skill_manager = SkillManagerAdapter(skill_engine)
        print(f"  技能管理器初始化完成 (加载 {len(skill_engine.list())} 个技能)")

        assistant_instance = LangGraphAgent(
            agent=langchain_agent,
            rag_workflow=rag_workflow,
            checkpointer=checkpointer,
            feeling_detector=feeling_detector,
            task_planner=task_planner,
            reflection_checker=reflection_checker,
            skill_manager=skill_manager
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
            "model": "qwen3.5-flash",
            "features": ["feeling_detection", "RAG", "tool_calling"]
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


if __name__ == '__main__':
    init_system()
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
