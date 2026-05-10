# 智能客服系统

基于 AI 的智能客服系统，采用前后端分离架构，支持知识库检索（RAG）、工具调用和多轮对话。系统已迁移至 **LangGraph** 架构，支持状态管理和工作流编排。

## 特色功能

- **智能知识库**: 基于向量数据库的语义检索，支持 .txt、.pdf、.docx 等文档格式
- **多知识库支持**: 支持多个独立知识库（产品文档、政策文件等），智能路由选择
- **模块化 RAG 框架**: 检索增强生成技术，支持多种索引器、检索器和生成策略组合
- **智能路由**: 基于 LLM 的智能路由器，自动判断是否需要检索及选择哪个知识库
- **查询扩展**: 使用 LLM 扩展用户查询，生成多个相关查询词提高召回率
- **上下文管理**: 独立会话管理，支持多轮对话和上下文记忆
- **工具调用**: AI 自动判断并调用外部工具（天气查询、天气推荐、表单提交），支持链式调用
- **MCP 架构**: 工具独立部署，支持多个 Agent 共享调用
- **Streamable HTTP**: 基于 HTTP 的流式传输协议，支持实时响应
- **情绪感知**: 基于关键词规则的情绪分析（default、upbeat、angry、cheerful、depressed、friendly），动态更新 Prompt
- **FewShot 示例学习**: 基于 LengthBasedExampleSelector 的动态示例选择
- **前后端分离**: React + Vite 前端 + Flask 后端
- **模块化设计**: 清晰的后端架构，易于扩展
- **LangGraph 集成**: 基于状态图的工作流编排，支持持久化检查点

## 项目结构

```
chart-flow-longchain/
├── backend/                    # Python 后端 (Flask)
│   ├── app.py                 # Flask 主应用入口
│   ├── requirements.txt       # Python 依赖
│   ├── modules/               # 核心功能模块
│   │   ├── __init__.py       # 模块包初始化
│   │   ├── ai_client.py       # AI 客户端（兼容 OpenAI SDK）
│   │   ├── assistant.py       # AI 助手/Agent（旧版）
│   │   ├── checkpoint/        # 检查点存储（独立模块）
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── memory.py
│   │   │   ├── redis.py
│   │   │   └── factory.py
│   │   ├── langgraph/         # LangGraph 模块（新版）
│   │   │   ├── __init__.py
│   │   │   ├── agent.py       # LangGraph Agent（状态图定义）
│   │   │   └── state.py       # 状态定义
│   │   ├── feeling/           # 情绪感知模块
│   │   │   ├── __init__.py
│   │   │   └── detector.py    # 情绪检测器
│   │   ├── rag/               # 模块化 RAG 框架（含 RAGWorkflow）
│   │   │   ├── __init__.py
│   │   │   ├── rag_chain.py   # RAG 链核心
│   │   │   ├── indexer/       # 索引模块
│   │   │   │   ├── base.py    # 索引器基类
│   │   │   │   ├── chroma.py  # Chroma 实现
│   │   │   │   └── milvus.py  # Milvus 实现
│   │   │   ├── retriever/     # 检索模块
│   │   │   │   ├── base.py    # 检索器基类
│   │   │   │   ├── simple.py  # 简单向量检索
│   │   │   │   ├── reranking.py  # 重排序检索
│   │   │   │   └── filtered.py   # 过滤检索
│   │   │   ├── generator/     # 生成模块
│   │   │   │   ├── base.py    # 生成器基类
│   │   │   │   ├── stuff.py   # Stuff 策略
│   │   │   │   ├── map_reduce.py  # Map-Reduce 策略
│   │   │   │   └── refine.py   # Refine 策略
│   │   │   ├── memory/        # 记忆模块
│   │   │   │   ├── base.py    # 记忆基类
│   │   │   │   ├── conversation.py  # 对话记忆
│   │   │   │   └── knowledge.py     # 知识记忆（预留）
│   │   │   └── router/        # 路由模块
│   │   │       ├── base.py    # 路由基类
│   │   │       ├── simple.py  # 简单路由
│   │   │       └── llm_router.py  # 基于LLM的智能路由
│   │   ├── document_loaders/  # 文档加载器
│   │   │   ├── __init__.py
│   │   │   ├── loader_factory.py
│   │   │   ├── text_loader.py
│   │   │   ├── pdf_loader.py
│   │   │   └── docx_loader.py   # 支持多种文档格式加载
│   │   ├── prompt/            # Prompt 模板管理
│   │   │   └── __init__.py    # 包含 FewShot 和 LengthBasedExampleSelector
│   │   └── rate_limit/        # 限流模块
│   │       ├── __init__.py
│   │       ├── langchain.py
│   │       └── rate_limiter.py
│   ├── mcp_module/            # MCP 模块（工具服务）
│   │   ├── __init__.py         # MCP 模块初始化
│   │   ├── config.py           # MCP 配置常量
│   │   ├── logger.py           # 统一日志模块
│   │   ├── mcp_server.py       # MCP 服务器核心
│   │   ├── mcp_client.py       # MCP 客户端
│   │   ├── mcp_service.py      # MCP 服务封装
│   │   ├── start.py            # MCP 服务器启动脚本
│   │   └── tools/              # 工具插件目录
│   │       ├── __init__.py
│   │       ├── registry.py     # 工具注册中心
│   │       ├── weather_plugin.py
│   │       ├── weather_recommend_plugin.py
│   │       └── submit_form_plugin.py
│   ├── knowledge_base/        # 知识库文档目录
│   │   ├── default/          # 默认知识库（产品文档等）
│   │   └── politics/         # 政策文档知识库
│   └── db/                    # 向量数据库存储目录

├── frontend/                   # React 前端 (Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatArea.jsx
│   │   │   ├── Header.jsx
│   │   │   └── InputArea.jsx
│   │   └── api/
│   │       └── chat.js
│   └── package.json
├── .env                       # 环境变量配置
└── .gitignore
```

## LangGraph 架构

系统已迁移至 LangGraph 架构，实现状态管理和工作流编排。

### 架构设计原则

1. **分离图定义与业务逻辑**: 将状态图定义与具体业务逻辑分离，提升可维护性
   - `LangGraphAgent` (agent.py): 负责定义状态图结构（节点、边、路由）
   - `RAGWorkflow` (rag.py): 负责实现具体业务功能（检索、生成等）

2. **状态持久化**: 通过检查点（Checkpoint）机制实现会话状态的持久化存储

3. **工作流编排**: 支持多节点路由、条件分支、循环等复杂工作流

### 状态图结构

```
START → feeling_detect → router → ┌── 需要检索 ──→ retrieve → generate → call_model → END
                                  │
                                  └── 不需要检索 ──→ call_model → END
```

### 核心节点

| 节点 | 职责 | 说明 |
|------|------|------|
| feeling_detect | 情绪检测 | 分析用户输入的情绪状态（default、upbeat、angry、cheerful、depressed、friendly） |
| router | 智能路由 | 判断是否需要检索、选择知识库 |
| retrieve | 文档检索 | 从向量数据库检索相关文档（支持查询扩展） |
| generate | 生成回答 | 基于检索文档生成 RAG 结果 |
| call_model | 模型调用 | 调用 LLM 生成最终回答，更新对话历史 |

### 状态定义

```python
class AgentState(TypedDict):
    query: str                    # 用户查询
    session_id: str               # 会话 ID
    feeling: dict                 # 情绪状态 {"feeling": str, "score": int}
    chat_history: List[BaseMessage] # 对话历史（统一管理）
    need_retrieve: bool           # 是否需要检索
    documents: List[Document]     # 检索到的文档
    answer: str                   # 生成的回答
```

## 情绪感知

系统支持基于关键词规则的情绪分析，每次对话前自动检测用户情绪状态，并动态更新 Prompt 模板。

### 情绪类型

| 情绪 | 描述 | 示例 |
|------|------|------|
| `default` | 中性/普通状态 | "随便吧，都可以" |
| `upbeat` | 积极向上 | "加油！我一定能做到" |
| `angry` | 愤怒不满 | "我特别生气！" |
| `cheerful` | 欢快喜悦 | "今天天气真好" |
| `depressed` | 消极低落 | "我很难过" |
| `friendly` | 友好亲切 | "谢谢你的帮助" |

### 情绪配置

每种情绪在 Prompt 中对应不同的 `roleSet` 和 `voiceStyle` 配置：

```python
MOODS = {
    "default": {"roleSet": "", "voiceStyle": "chat"},
    "upbeat": {"roleSet": "你觉得很开心...", "voiceStyle": "upbeat"},
    "angry": {"roleSet": "你会安慰用户...", "voiceStyle": "friendly"},
    "cheerful": {"roleSet": "你感到开心和兴奋...", "voiceStyle": "cheerful"},
    "depressed": {"roleSet": "你会鼓励用户...", "voiceStyle": "friendly"},
    "friendly": {"roleSet": "你感觉很友好...", "voiceStyle": "friendly"}
}
```

### 工作流程

```
用户输入 → 情绪检测 → 情绪匹配 → 动态更新 Prompt → 调用 LLM → 返回结果
              ↓
         检测结果包含:
         - feeling: 情绪类型
         - score: 情绪分值 (1-10)
```

## 模块化 RAG 框架

系统采用模块化 RAG 架构，将 RAG 流程拆分为可插拔的独立模块，支持自由组合和扩展。

### 模块结构

```
RAG 流程:
用户提问 → 智能路由 → 选择知识库 → 检索文档（含查询扩展）→ 生成回答 → 返回结果
           ↓           ↓           ↓                  ↓         ↓
         Router    Knowledge    Retriever          Generator
           ↓           ↓           ↓                  ↓
       LLMRouter   Multi KB    SimpleVector      BaseGenerator
                                    ↓
                              Chroma/Milvus
```

### 核心模块

| 模块 | 职责 | 基类 | 实现类 |
|------|------|------|--------|
| Indexer | 文档加载、切分、向量化存储 | BaseIndexer | ChromaIndexer, MilvusIndexer |
| Retriever | 从索引中检索相关文档 | BaseRetriever | SimpleVectorRetriever, RerankingRetriever, FilteredRetriever |
| Generator | 基于检索文档生成回答 | BaseGenerator | StuffGenerator, MapReduceGenerator, RefineGenerator |
| Memory | 管理对话历史和上下文 | BaseMemory | ConversationMemory, KnowledgeMemory |
| Router | 决定是否检索、选择知识库 | BaseRouter | SimpleRouter, LLMRouter |

### 多知识库支持

系统支持多个独立知识库，通过智能路由器自动选择合适的知识库：

| 知识库名称 | 用途 | 示例内容 |
|-----------|------|---------|
| default | 产品文档、公司信息 | 智能办公系统、数据分析平台、价格方案、售后服务 |
| politics | 政策文档 | 党的会议文件、政策文件 |

### 智能路由

LLMRouter 使用大语言模型分析用户问题，实现：

1. **判断是否需要检索**：区分需要知识库的问题和常识/创意问题
2. **选择知识库**：根据问题领域选择合适的知识库
3. **选择检索策略**：根据问题复杂度调整检索参数

### 查询扩展

RAGWorkflow 支持查询扩展功能，通过 LLM 生成多个相关查询词：

1. 接收用户原始查询
2. 使用 LLM 生成 3-5 个相关查询词
3. 对每个查询词执行检索
4. 合并结果并去重
5. 返回最终检索结果

## 快速开始

### 环境要求

- Python >= 3.10
- Node.js >= 16
- npm 或 yarn
- 阿里云百炼 API 密钥（或 OpenAI API）

### 后端启动

**第一步：启动 MCP 服务**

```bash
# 进入后端目录
cd backend

# 安装依赖（首次运行）
pip install -r requirements.txt

# 启动 MCP 服务器（独立部署）
python mcp_module/start.py
```

MCP 服务器运行在: `http://localhost:8080/mcp`

**第二步：启动应用服务**

```bash
# 新开终端，进入后端目录
cd backend

# 启动服务
python app.py
```

后端运行在: `http://localhost:5000`

### 前端启动

```bash
# 新开终端，进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在: `http://localhost:5173`

### 访问应用

浏览器打开: `http://localhost:5173`

## 配置说明

### .env 环境变量配置

```env
# AI API 配置
API_KEY=your_api_key
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL=qwen3.6-flash
EMBEDDING_MODEL=text-embedding-v3

# 向量数据库配置
VECTOR_STORE_TYPE=chroma
VECTOR_STORE_PERSIST_DIRECTORY=db/chroma
VECTOR_STORE_COLLECTION_NAME=knowledge_base

# 检查点存储配置
CHECKPOINT_STORAGE=memory
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=5000

# MCP 配置
MCP_HOST=0.0.0.0
MCP_PORT=8080
```

| 配置项 | 说明 |
|--------|------|
| API_KEY | 阿里云百炼或 OpenAI API 密钥 |
| BASE_URL | API 基础地址 |
| MODEL | 对话模型名称 |
| EMBEDDING_MODEL | 向量化模型名称 |
| CHECKPOINT_STORAGE | 检查点存储类型：`memory`（内存）或 `redis`（Redis持久化） |
| REDIS_HOST | Redis 服务器地址（当 CHECKPOINT_STORAGE=redis 时生效） |
| REDIS_PORT | Redis 端口号 |
| REDIS_DB | Redis 数据库编号 |
| REDIS_PASSWORD | Redis 密码（可选） |

### MCP 配置

MCP 服务器配置位于 `backend/mcp_module/config.py`:

```python
# MCP 服务器配置
MCP_HOST = "0.0.0.0"
MCP_PORT = 8080
MCP_PATH = "/mcp"
MCP_URL = f"http://127.0.0.1:{MCP_PORT}{MCP_PATH}"

# 应用服务器配置
APP_HOST = "0.0.0.0"
APP_PORT = 5000
```

## API 接口

### GET /start

检查服务状态。

**响应示例:**
```json
{
  "status": "ready",
  "message": "客服系统已就绪 (LangGraph)",
  "model": "qwen-plus",
  "knowledge_base": true
}
```

### POST /chat

处理对话请求。

**请求:**
```json
{
  "message": "用户输入",
  "session_id": "可选会话ID"
}
```

**响应:**
```json
{
  "reply": "AI回复内容",
  "feeling": {"feeling": "cheerful", "score": 3},
  "tool_calls": [],
  "session_id": "会话ID",
  "finished": false
}
```

## MCP 架构说明

### MCP 服务器

MCP（Model Context Protocol）服务器负责管理和提供工具服务：

```
┌─────────────────────────────────────────────────────┐
│                MCP 服务器 (8080端口)                 │
│  ┌─────────────────────────────────────────────┐   │
│  │           工具注册表 (_TOOL_REGISTRY)          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────┐   │   │
│  │  │get_weather│ │get_weather_forecast│ │submit_form│ │   │
│  │  └────┬────┘ └────┬────┘ └──────┬──────┘   │   │
│  └───────┼───────────┼─────────────┼───────────┘   │
│          │           │             │               │
│          └───────────┼─────────────┘               │
│                      ↓                             │
│            ┌─────────────────┐                     │
│            │  FastMCP Server │ ← Streamable HTTP   │
│            └─────────────────┘                     │
└─────────────────────────────────────────────────────┘
                          ↑
                          │ HTTP 请求
                          ↓
┌─────────────────────────────────────────────────────┐
│              应用服务器 (5000端口)                    │
│  ┌─────────────┐    ┌─────────────┐                │
│  │   Agent     │←───│MCPToolService│                │
│  │ (LangGraph) │    │   (客户端)   │                │
│  └─────────────┘    └─────────────┘                │
└─────────────────────────────────────────────────────┘
```

### 工具注册机制

工具通过装饰器注册到全局注册表：

```python
from mcp_module.tools.registry import register_tool

@register_tool(
    name="get_weather",
    description="查询指定城市的实时天气",
    parameters=[
        {
            "name": "city",
            "type": "string",
            "description": "要查询天气的城市名称",
            "required": True
        }
    ],
    return_type="string"
)
def get_weather(city: str) -> str:
    # 工具实现...
```

## 使用流程

1. **准备知识库**: 在 `backend/knowledge_base/` 目录添加文档（支持 .txt、.pdf、.docx）
2. **启动 MCP 服务器**: `python backend/mcp_module/start.py`
3. **启动应用服务器**: `python backend/app.py`
4. **开始对话**: 访问前端地址，与智能客服对话
5. **RAG 增强**: 系统自动从知识库检索相关内容，增强 AI 回答
6. **工具调用**: AI 通过 MCP 服务器调用天气查询、推荐或表单提交等工具
7. **FewShot 学习**: 系统使用默认示例对话，也可自定义示例

## 自定义扩展

### 修改系统提示词

编辑 `backend/modules/prompt/__init__.py` 中的 `PromptClass` 类，可以修改 `SystemPrompt` 和 `MOODS` 配置

### 自定义 FewShot 示例

在 `backend/modules/prompt/__init__.py` 中修改 `DEFAULT_FEW_SHOT_EXAMPLES` 列表：

```python
DEFAULT_FEW_SHOT_EXAMPLES = [
    {"user_query": "你好", "assistant_response": "您好！请问有什么可以帮助您的？"},
    {"user_query": "你们有什么产品?", "assistant_response": "我们提供多种优质产品..."},
]
```

### 添加新工具

1. 在 `backend/mcp_module/tools/` 创建插件文件
2. 使用 `@register_tool` 装饰器注册工具
3. 在 `start.py` 中导入工具模块
4. 重启 MCP 服务

```python
# 示例工具插件
from mcp_module.tools.registry import register_tool

@register_tool(
    name="my_tool",
    description="我的自定义工具",
    parameters=[...],
    return_type="string"
)
def my_tool(param1: str) -> str:
    return "工具执行结果"
```

### 更新知识库

1. 在 `backend/knowledge_base/` 添加或修改文档
2. 重启服务，系统自动重新向量化

### 扩展 RAG 模块

各模块基类提供默认实现，未实现的模块返回空结果或警告日志：

```python
# 基类默认行为
BaseIndexer.build_index()    # 返回错误状态
BaseRetriever.retrieve()    # 返回空列表
BaseGenerator.generate()     # 返回空字符串
BaseMemory.add_message()     # 无操作
BaseRouter.should_retrieve() # 返回 True
```

## 技术栈

**后端:**
- Flask 3.0.0 - Web 框架
- OpenAI SDK >= 1.40.0 - AI API 客户端（兼容 DeepSeek）
- Flask-CORS - 跨域支持
- Flask-Limiter - 限流支持
- numpy 2.4.4 - 数值计算
- LangChain >= 0.3.0 - Agent 和工具框架
- LangChain Core >= 0.3.0 - 核心组件
- LangChain Community >= 0.3.0 - 社区组件
- LangGraph >= 0.1.0 - 状态图工作流框架
- langchain-chroma >= 0.1.0 - Chroma 集成
- chromadb >= 0.5.0 - 向量数据库
- pymilvus >= 2.4.0 - Milvus 支持（可选）
- redis >= 5.0.0 - Redis 支持（可选，用于检查点持久化）
- dashscope >= 1.20.0 - 阿里云百炼支持（可选）
- MCP - Model Context Protocol（工具服务协议）

**前端:**
- React 18 - UI 框架
- Vite - 构建工具
- Axios - HTTP 请求

**AI 服务:**
- 阿里云百炼平台 / OpenAI
- qwen-plus 模型
- text-embedding-v3 向量化模型

**向量数据库:**
- Chroma - 默认向量存储
- Milvus - 可选向量存储

## 后续优化

- [x] MCP 架构迁移
- [x] 工具独立部署
- [x] Streamable HTTP 支持
- [x] 统一日志模块
- [x] 集中配置管理
- [x] 模块化 RAG 框架
- [x] 限流模块集成
- [x] 多知识库支持
- [x] 智能路由（LLMRouter）
- [x] 查询扩展功能
- [x] LangGraph 架构迁移
- [x] 状态持久化检查点

### 检查点存储

系统支持两种检查点存储方式，通过 `CHECKPOINT_STORAGE` 环境变量配置：

**1. MemorySaver（内存存储）**
- 默认配置，适合开发和测试环境
- 数据存储在内存中，服务重启后数据丢失
- 配置：`CHECKPOINT_STORAGE=memory`

**2. RedisSaver（Redis 持久化存储）**
- 适合生产环境，支持会话持久化
- 需要提前启动 Redis 服务
- 配置：`CHECKPOINT_STORAGE=redis`

**Redis 启动方式：**

```bash
# 使用 Docker（推荐）
docker run -d -p 6379:6379 redis

# 或本地安装的 Redis
redis-server
```

**检查点工厂模式：**

系统采用工厂模式管理检查点存储，支持动态注册和扩展：

```python
# 注册存储实现
CheckpointFactory.register("memory", MemorySaver)
CheckpointFactory.register("redis", RedisSaver)

# 构建实例
checkpointer = CheckpointFactory.build(name="memory")
```

- [ ] 数据库替代 JSON 存储
- [ ] API 安全验证
- [ ] Docker 容器化部署
