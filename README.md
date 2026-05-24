# 智能客服系统

基于 AI 的智能客服系统，采用前后端分离架构，支持知识库检索（RAG）、工具调用和多轮对话。系统已迁移至 **LangGraph** 架构，支持状态管理和工作流编排。

## 特色功能

- **智能知识库**: 基于向量数据库的语义检索，支持 .txt、.pdf、.docx 等文档格式，可通过配置中心管理
- **多知识库支持**: 支持多个独立知识库（产品文档、政策文件等），智能路由选择
- **可视化知识库管理**: 通过前端 UI 动态管理知识库，支持创建、删除知识库，上传文档并自动向量化
- **配置中心**: 统一管理系统配置，包括技能安装、MCP 工具配置、数据库（向量库）管理等，无需手动修改配置文件
- **模块化 RAG 框架**: 检索增强生成技术，支持多种索引器、检索器和生成策略组合
- **智能路由**: 基于 LLM 的智能路由器，自动判断是否需要检索及选择哪个知识库
- **查询扩展**: 使用 LLM 扩展用户查询，生成多个相关查询词提高召回率
- **上下文管理**: 独立会话管理，支持多轮对话和上下文记忆
- **工具调用**: AI 自动判断并调用外部工具（天气查询、天气推荐、表单提交），支持链式调用
- **钉钉集成**: 支持钉钉日程管理（创建、查询、删除日程）和待办事项
- **MCP 多服务器**: 支持从多个 MCP 服务器获取工具，实现工具服务的分布式部署，可通过配置中心动态添加/删除 MCP 服务器
- **MCP 架构**: 工具独立部署，支持多个 Agent 共享调用，可通过配置中心管理 MCP 工具
- **情绪感知**: 基于关键词规则的情绪分析（default、upbeat、angry、cheerful、depressed、friendly），动态更新 Prompt
- **智能任务规划**: 基于 LLM 的问题难度评估（1-5级），自动生成多步骤执行计划，支持工具调用与任务规划的深度整合
- **技能系统**: 基于 SKILL.md 的技能匹配和执行引擎，支持数据分析、绘图、旅行规划等专业技能，可通过配置中心安装/管理技能
- **前后端分离**: React + Vite 前端 + Flask 后端
- **模块化设计**: 清晰的后端架构，易于扩展
- **LangGraph 集成**: 基于状态图的工作流编排，支持持久化检查点

## 项目结构

```
chart-flow-longgraph/
├── backend/                      # Python 后端 (Flask)
│   ├── app.py                   # Flask 主应用入口
│   ├── db.py                    # 向量库管理 API
│   ├── DingWebHook.py           # 钉钉 Webhook 入口
│   ├── Dockerfile               # Docker 构建文件
│   ├── docker-compose.yml       # Docker Compose 配置
│   ├── requirements.txt         # Python 依赖
│   ├── api/                     # API 接口层
│   ├── config/                  # 配置文件
│   ├── gateway/                 # 网关配置（Nginx 配置）
│   ├── modules/                 # 核心功能模块
│   │   ├── __init__.py          # 模块包初始化
│   │   ├── ai_client.py         # AI 客户端（兼容 OpenAI SDK）
│   │   ├── assistant.py         # AI 助手/Agent（旧版）
│   │   ├── factory.py           # 工厂函数
│   │   ├── logger.py            # 统一日志模块
│   │   ├── tools.py             # 工具函数
│   │   ├── checkpoint/          # 检查点存储
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── memory.py
│   │   │   ├── redis.py
│   │   │   └── factory.py
│   │   ├── langgraph/           # LangGraph 模块
│   │   │   ├── __init__.py
│   │   │   ├── agent.py         # LangGraph Agent（状态图定义）
│   │   │   ├── state.py         # 状态定义
│   │   │   ├── states/          # 状态类型
│   │   │   ├── planner/         # 任务规划器
│   │   │   ├── reflection/      # 反思校验器
│   │   │   └── task_generators/ # 任务生成器（责任链模式）
│   │   ├── feeling/             # 情绪感知模块
│   │   ├── rag/                 # 模块化 RAG 框架
│   │   │   ├── __init__.py
│   │   │   ├── rag.py           # RAG 工作流核心
│   │   │   ├── indexer/         # 索引模块
│   │   │   ├── retriever/       # 检索模块
│   │   │   ├── generator/       # 生成模块
│   │   │   └── router/          # 路由模块
│   │   ├── document_loaders/    # 文档加载器
│   │   ├── prompt/              # Prompt 模板管理
│   │   ├── rate_limit/          # 限流模块
│   │   └── skill/               # 技能系统模块
│   │       ├── __init__.py
│   │       ├── loader.py        # 技能加载器（pydantic-ai-skills）
│   │       ├── matcher.py       # 技能匹配器
│   │       ├── executor.py      # 脚本执行器
│   │       ├── manager.py       # 生命周期管理
│   │       ├── models.py        # 数据模型
│   │       └── tools/           # LangChain 工具封装
│   ├── mcp_module/              # MCP 模块（工具服务）
│   │   ├── __init__.py
│   │   ├── config.py            # MCP 配置常量
│   │   ├── context.py           # MCP 上下文
│   │   ├── logger.py            # 日志模块
│   │   ├── mcp_server.py        # MCP 服务器核心
│   │   ├── mcp_client.py        # MCP 客户端
│   │   ├── mcp_config_manager.py# MCP 配置管理
│   │   ├── mcp_service.py       # MCP 服务封装
│   │   ├── start.py             # 启动脚本
│   │   └── tools/               # 工具插件目录
│   ├── knowledge_base/          # 知识库管理模块
│   ├── db/                      # 向量数据库存储（Chroma）
│   ├── user/                    # 用户管理模块
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── memory.py
│   │   └── redis.py
│   └── skills/                  # 技能库（SKILL.md 格式）
├── frontend/                    # React 前端 (Vite)
│   ├── src/
│   │   ├── api/                 # API 接口封装
│   │   ├── components/          # React 组件
│   │   │   ├── chat/            # 聊天组件
│   │   │   ├── config/          # 配置管理组件
│   │   │   ├── vectorDbManagerComponents/  # 向量库管理组件
│   │   │   └── preview/         # 文件预览组件
│   │   │       └── previews/    # 预览器（Word/Excel/PDF/Text）
│   │   ├── constants/           # 常量定义
│   │   ├── hooks/               # 自定义 Hooks
│   │   └── stores/              # 状态管理（Zustand）
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile
│   └── nginx.conf
├── resources/                   # 资源文件
├── .env                         # 环境变量配置
└── .gitignore
```

## LangGraph 架构

系统已迁移至 LangGraph 架构，实现状态管理和工作流编排。

### 架构设计原则

1. **分离图定义与业务逻辑**: 将状态图定义与具体业务逻辑分离，提升可维护性
   - `LangGraphAgent` (agent.py): 负责定义状态图结构（节点、边、路由）
   - `ContextBuilder` (context_builder.py): 负责上下文构建（RAG 文档、对话历史等）
   - `RAGWorkflow` (rag.py): 负责实现具体业务功能（检索、生成等）
2. **分离调度层与执行层**: LangGraph 负责流程编排，LangChain Agent 负责具体执行
   - LangGraph（调度层）：不包含技能相关节点，专注于流程控制
   - LangChain Agent（执行层）：通过 tool calling 自主调用技能工具
3. **状态持久化**: 通过检查点（Checkpoint）机制实现会话状态的持久化存储
4. **工作流编排**: 支持多节点路由、条件分支、循环等复杂工作流

### 状态图结构

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              LangGraph 状态图                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘

START → feeling_detect → router → ┌── 需要检索 ──→ retrieve → generate → plan
                                   │                                        │
                                   └── 不需要检索 ──→ plan ←─────────────────┘
                                                        │
                                                        ▼
                                      execute_task → check_task_complete → ┌── 有更多任务 ──→ execute_task
                                                                           │
                                                                           └── 所有任务完成 ──→ call_model → END
```

### execute\_task 节点详解

`execute_task` 是核心执行节点，通过 **LangChain Agent** 调用工具：

```
execute_task
    │
    ▼
LangChain Agent.invoke()
    │
    ├─── MCP 工具调用（通过 MCPToolService）────────────────────────────┐
    │                                                                     │
    │   ├── tool: weather_query        # 天气查询                         │
    │   ├── tool: weather_recommend    # 天气推荐                         │
    │   ├── tool: submit_form          # 表单提交                         │
    │   ├── tool: dingtalk_schedule    # 钉钉日程                         │
    │   └── tool: dingtalk_todo        # 钉钉待办                         │
    │                                                                     │
    ├─── 技能工具调用（通过 Skill Tools）─────────────────────────────────┤
    │                                                                     │
    │   注意：技能执行已从 LangGraph 节点转移到 LangChain Agent           │
    │   Agent 通过 skill_list 发现技能，skill_instructions 加载指令       │
    │   自主执行技能任务，无需经过 LangGraph 调度                          │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
```

### 节点说明

| 节点                    | 职责   | 说明                                      |
| --------------------- | ---- | --------------------------------------- |
| `feeling_detect`      | 情绪检测 | 检测用户情绪，动态更新 Prompt              |
| `router`              | 智能路由 | 判断是否需要检索，选择知识库                |
| `retrieve`            | 文档检索 | 从向量库检索相关文档                       |
| `generate`            | 生成回答 | 基于检索结果生成回答                       |
| `plan`                | 任务规划 | 评估问题难度，拆分子任务（RAG 增强）         |
| `execute_task`        | 执行任务 | **核心节点**：调用 MCP 工具（LangChain Agent 执行） |
| `check_task_complete` | 检查完成 | 判断是否还有子任务                        |
| `call_model`          | 调用模型 | 最终回复生成                              |

**注意**: 技能执行已从 LangGraph 调度层转移到 LangChain Agent，通过 tool calling 自主发现和执行技能。

## 情绪感知

系统支持基于关键词规则的情绪分析，每次对话前自动检测用户情绪状态，并动态更新 Prompt 模板。

### 情绪类型

| 情绪          | 描述      | 示例          |
| ----------- | ------- | ----------- |
| `default`   | 中性/普通状态 | "随便吧，都可以"   |
| `upbeat`    | 积极向上    | "加油！我一定能做到" |
| `angry`     | 愤怒不满    | "我特别生气！"    |
| `cheerful`  | 欢快喜悦    | "今天天气真好"    |
| `depressed` | 消极低落    | "我很难过"      |
| `friendly`  | 友好亲切    | "谢谢你的帮助"    |

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

## 智能任务规划

系统支持基于 LLM 的智能任务规划，根据问题难度自动生成多步骤执行计划。

### 难度等级划分

| 难度等级 | 描述        | 任务数量 | 示例              |
| ---- | --------- | ---- | --------------- |
| 1级   | 简单事实查询    | 1个任务 | "北京今天天气怎么样？"    |
| 2级   | 需要简单推理    | 1个任务 | "明天去上海出差需要带什么？" |
| 3级   | 需要多步骤分析   | 2个任务 | "帮我分析本月销售数据"    |
| 4级   | 需要综合多领域知识 | 3个任务 | "制定下周旅行计划"      |
| 5级   | 需要创造性解决方案 | 4个任务 | "设计一个新产品推广方案"   |

### 任务规划流程

```
用户查询 → 难度评估 → ┌── 简单(1-2级) ──→ 直接回答
                   │
                   └── 复杂(3-5级) ──→ 任务拆分 → 有序子任务列表
```

### 配置项

| 环境变量                      | 默认值  | 说明       |
| ------------------------- | ---- | -------- |
| TASK\_PLANNER\_MAX\_TASKS | 5    | 最大子任务数量  |
| TASK\_PLANNER\_MIN\_TASKS | 1    | 最小子任务数量  |
| TASK\_PLANNER\_ENABLE     | true | 是否启用任务规划 |

## 技能系统

基于 `pydantic-ai-skills` 的技能匹配和执行引擎，提供专业领域的深度服务。

> 📖 **详细设计文档**: [SKILL\_SYSTEM.md](SKILL_SYSTEM.md)
>
> 包含：技术架构、执行流程图、安装流程、目录结构、SKILL.md 格式、开发指南、API 接口

### 核心特性

- **业界成熟方案**: 使用 `pydantic-ai-skills.SkillsToolset` 加载和管理技能
- **分层架构**: Loader → Matcher → Executor → Tools → Manager
- **渐进式披露**: skill\_list → skill\_instructions → skill\_reference → skill\_save\_file → skill\_run\_script
- **GitHub 安装**: 支持从 GitHub URL 一键安装技能

### 内置技能

| 技能名称          | 功能描述       |
| ------------- | ---------- |
| data-analysis | 数据分析、可视化报告 |
| drawio-skill  | 流程图、架构图绘制  |
| tldraw-skill  | 协作绘图、白板    |
| trip-plan     | 旅行规划、行程安排  |

### 快速开始

```python
from api.skill_installer import get_installer

installer = get_installer()
installer.install_from_url("https://github.com/Agents365-ai/drawio-skill")
skills = installer.list_installed()
```

## 配置中心

系统提供统一的配置中心，通过前端界面管理所有配置项，无需手动修改配置文件。

### 功能模块

配置中心包含以下管理功能：

| 功能                 | 说明                          |
| ------------------ | --------------------------- |
| **技能管理**           | 安装、卸载、配置技能，可通过管理页面动态添加新技能   |
| **MCP 工具配置**       | 添加、删除 MCP 服务器，配置 MCP 工具连接参数 |
| **数据库管理（RAG 向量库）** | 创建、删除向量数据库，上传文档，管理知识库       |
| **钉钉文字仓颉编辑器**      | 集成钉钉文字仓颉编辑器，支持 Word 文档在线预览 |
| **钉钉表格纵横 SDK**     | 集成钉钉表格纵横 SDK，支持 Excel 文件在线预览 |
| **PDF 文件预览**       | 支持 PDF 文件在线预览，无需下载即可查看文档内容 |

### 技能管理

通过配置中心可以：

- **安装技能**: 从预置技能列表中选择安装，或导入自定义技能
- **卸载技能**: 删除不需要的技能

### MCP 工具配置

通过配置中心可以：

- **添加 MCP 服务器**: 输入服务器地址和认证信息，自动连接
- **删除 MCP 服务器**: 移除不需要的 MCP 服务器连接
- **工具列表**: 查看已连接 MCP 服务器提供的工具

### 数据库管理（RAG 向量库）

通过配置中心可以：

- **创建知识库**: 创建新的向量数据库，设置名称和描述
- **删除知识库**: 删除不需要的知识库及其索引数据
- **上传文档**: 上传 .txt、.pdf、.docx 格式的文档，自动向量化

### 钉钉文字仓颉编辑器

集成钉钉文字仓颉编辑器，提供文档在线预览能力。

官网：https://page.dingtalk.com/app/we-editor/site/index.html?spm=a2q1e.24441682.0.0.202e789eXdrRGA

功能特性：

- **Word 文档预览**: 在线预览 .doc、.docx 格式文档，无需下载
- **格式保留**: 完整保留文档格式、样式、表格等元素
- **高清渲染**: 保持文档原始排版和清晰度

### 钉钉表格纵横 SDK

集成钉钉表格纵横 SDK，提供表格在线预览能力。

官网：https://page.dingtalk.com/app/alidocs/zongheng-site/index.html#/

功能特性：

- **Excel 文件预览**: 在线预览 .xls、.xlsx 格式文件，支持复杂表格
- **格式兼容**: 完美兼容 Excel 各种格式和功能
- **高清渲染**: 保持表格原始排版和清晰度

### PDF 文件预览

支持 PDF 文件的在线预览功能：

- **PDF 文档预览**: 在线预览 .pdf 格式文件，无需下载即可查看
- **高清渲染**: 保持文档原始排版和清晰度
- **快速加载**: 优化加载速度，提升用户体验
- **多页浏览**: 支持多页 PDF 文档的流畅浏览

### 访问配置中心

配置中心前端界面访问地址：`http://localhost:5174`（向量库管理界面）

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

| 模块        | 职责            | 基类            | 实现类                                                          |
| --------- | ------------- | ------------- | ------------------------------------------------------------ |
| Indexer   | 文档加载、切分、向量化存储 | BaseIndexer   | ChromaIndexer, MilvusIndexer                                 |
| Retriever | 从索引中检索相关文档    | BaseRetriever | SimpleVectorRetriever, RerankingRetriever, FilteredRetriever |
| Generator | 基于检索文档生成回答    | BaseGenerator | StuffGenerator, MapReduceGenerator, RefineGenerator          |
| Memory    | 管理对话历史和上下文    | BaseMemory    | ConversationMemory, KnowledgeMemory                          |
| Router    | 决定是否检索、选择知识库  | BaseRouter    | SimpleRouter, LLMRouter                                      |

### 多知识库支持

系统支持多个独立知识库，通过智能路由器自动选择合适的知识库：

| 知识库名称    | 用途        | 示例内容                    |
| -------- | --------- | ----------------------- |
| default  | 产品文档、公司信息 | 智能办公系统、数据分析平台、价格方案、售后服务 |
| politics | 政策文档      | 党的会议文件、政策文件             |
| exams    | 考试资料      | 行测蒙题技巧、考试复习资料           |

### 可视化知识库管理

系统提供前端 UI 支持知识库的动态管理：

- **创建知识库**: 通过前端界面创建新的知识库，自动生成对应的目录和索引
- **删除知识库**: 删除不需要的知识库，同时清理相关的向量索引
- **上传文档**: 支持上传 .txt、.pdf、.docx 格式的文档
- **自动向量化**: 上传的文档会自动进行切分、向量化并建立索引
- **文档管理**: 查看、删除已上传的文档，支持重新索引

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
MODEL=qwen3.5-flash
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
MCP_SERVERS=[{"name":"default","url":"http://localhost:8080/mcp"}]

# 钉钉配置（可选）
DINGTALK_CLIENT_ID=your_app_key
DINGTALK_CLIENT_SECRET=your_app_secret
```

| 配置项                 | 说明                                           |
| ------------------- | -------------------------------------------- |
| API\_KEY            | 阿里云百炼或 OpenAI API 密钥                         |
| BASE\_URL           | API 基础地址                                     |
| MODEL               | 对话模型名称                                       |
| EMBEDDING\_MODEL    | 向量化模型名称                                      |
| CHECKPOINT\_STORAGE | 检查点存储类型：`memory`（内存）或 `redis`（Redis持久化）      |
| REDIS\_HOST         | Redis 服务器地址（当 CHECKPOINT\_STORAGE=redis 时生效） |
| REDIS\_PORT         | Redis 端口号                                    |
| REDIS\_DB           | Redis 数据库编号                                  |
| REDIS\_PASSWORD     | Redis 密码（可选）                                 |
| MCP\_SERVERS        | MCP 服务器配置列表，支持多服务器配置                         |

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

### 向量库管理 API

#### GET /api/databases

获取所有知识库列表。

**响应:**

```json
{
  "status": "success",
  "data": [
    {
      "name": "default",
      "description": "默认知识库",
      "document_count": 5,
      "vector_count": 128,
      "created_at": "2024-01-01 10:00:00"
    }
  ]
}
```

#### POST /api/databases

创建新的知识库。

**请求:**

```json
{
  "name": "my_knowledge_base",
  "description": "我的知识库"
}
```

**响应:**

```json
{
  "status": "success",
  "message": "数据库创建成功",
  "data": {"name": "my_knowledge_base", "description": "我的知识库"}
}
```

#### GET /api/databases/{db\_name}

获取指定知识库详情。

**响应:**

```json
{
  "status": "success",
  "data": {
    "name": "default",
    "description": "默认知识库",
    "document_count": 5,
    "vector_count": 128,
    "documents": ["file1.txt", "file2.pdf"],
    "created_at": "2024-01-01 10:00:00",
    "updated_at": "2024-01-02 14:30:00"
  }
}
```

#### PUT /api/databases/{db\_name}

更新知识库信息。

**请求:**

```json
{
  "description": "更新后的描述"
}
```

**响应:**

```json
{
  "status": "success",
  "message": "数据库信息更新成功"
}
```

#### DELETE /api/databases/{db\_name}

删除知识库（同时删除向量索引）。

**响应:**

```json
{
  "status": "success",
  "message": "数据库删除成功"
}
```

#### POST /api/databases/{db\_name}/upload

上传文档到知识库并自动向量化。

**请求:** `multipart/form-data`

```
files: [file1.txt, file2.pdf, file3.docx]
```

**响应:**

```json
{
  "status": "success",
  "message": "文件上传成功",
  "data": {
    "uploaded_files": ["file1.txt", "file2.pdf"],
    "vector_count": 256
  }
}
```

## MCP 架构说明

### MCP 服务器

MCP（Model Context Protocol）服务器负责管理和提供工具服务：

```
┌───────────────────────────────────────────────────────┐
│                MCP 服务器 (8080端口)                    │
│  ┌────────────────────────────────────────────────────┐
│  │           工具注册表 (_TOOL_REGISTRY)                │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────┐           │
│  │  │get_weather│ │get_weather_forecast│  │           │
│  │  └────┬────┘ └────┬────┘ └──────┬──────┘           │
│  └───────┼───────────┼─────────────┼                  │
│          │           │             │                  │
│          └───────────┼─────────────┘                  │
│                      ↓                                │
│            ┌─────────────────┐                        │
│            │  FastMCP Server │ ← Streamable HTTP      │
│            └─────────────────┘                        │
└───────────────────────────────────────────────────────┘
                          ↑
                          │ HTTP 请求
                          ↓
┌─────────────────────────────────────────────────────┐
│              应用服务器 (5000端口)                    │
│  ┌─────────────┐    ┌─────────────┐                 │
│  │   Agent     │←───│MCPToolService│                │
│  │ (LangGraph) │    │   (客户端)   │                 │
│  └─────────────┘    └─────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### MCP 多服务器支持

系统支持从多个 MCP 服务器获取工具，实现工具服务的分布式部署：

```python
# config.py
MCP_SERVERS = [
    {"name": "default", "url": "http://localhost:8080/mcp"},
    {"name": "dingtalk", "url": "http://localhost:8081/mcp"},
    {"name": "custom", "url": "http://custom-server:8080/mcp"}
]
```

`MCPToolService` 会自动连接所有配置的服务器并合并工具列表。

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

## 钉钉集成

系统支持钉钉工具调用，包括日程管理和待办事项功能。

### 钉钉工具列表

| 工具名称                       | 功能   | 参数                                                |
| -------------------------- | ---- | ------------------------------------------------- |
| `create_dingtalk_schedule` | 创建日程 | summary(标题), isAllDay(是否全天), start/end datetime 等 |
| `query_dingtalk_schedule`  | 查询日程 | schedule\_id 或查询条件                                |
| `delete_dingtalk_schedule` | 删除日程 | schedule\_id                                      |
| `create_dingtalk_todo`     | 创建待办 | summary(标题), due\_date(截止日期)                      |

### 钉钉配置

在 `.env` 文件中添加钉钉配置：

```env
DINGTALK_CLIENT_ID=your_app_key
DINGTALK_CLIENT_SECRET=your_app_secret
```

### 日程参数说明

创建日程时需要注意全天和非全天日程的参数差异：

| 参数              | 全天日程 | 非全天日程 |
| --------------- | ---- | ----- |
| start\_date     | ✅ 必填 | ❌ 留空  |
| start\_datetime | ❌ 留空 | ✅ 必填  |
| end\_date       | ✅ 必填 | ❌ 留空  |
| end\_datetime   | ❌ 留空 | ✅ 必填  |
| isAllDay        | true | false |

## 使用流程

1. **准备知识库**: 在 `backend/knowledge_base/` 目录添加文档（支持 .txt、.pdf、.docx）
2. **启动 MCP 服务器**: `python backend/mcp_module/start.py`
3. **启动应用服务器**: `python backend/app.py`
4. **开始对话**: 访问前端地址，与智能客服对话
5. **RAG 增强**: 系统自动从知识库检索相关内容，增强 AI 回答
6. **工具调用**: AI 通过 MCP 服务器调用天气查询、推荐或表单提交等工具
7. **钉钉功能**: AI 可以帮用户创建、查询、删除钉钉日程和待办事项
8. **FewShot 学习**: 系统使用默认示例对话，也可自定义示例

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
- [x] 智能任务规划（Task Planner）
- [x] 反思校验器（Reflection Checker）
- [x] 技能系统（Skill System）
- [x] 技能匹配与执行引擎

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

## Docker 容器化部署

系统已支持 Docker 容器化部署，可通过 `docker-compose` 一键启动所有服务。

### Docker 服务架构

| 服务                | 端口   | 说明          |
| ----------------- | ---- | ----------- |
| `redis`           | 6379 | 会话状态存储      |
| `mcp`             | 8080 | MCP 工具服务器   |
| `app`             | 8000 | 智能客服后端 API  |
| `db`              | 5001 | 向量库管理后端 API |
| `vector-frontend` | 5174 | 向量库管理前端 UI  |

### Docker 部署步骤

```bash
# 进入后端目录
cd backend

# 使用 Docker Compose 启动所有服务
docker-compose up -d
```

### 访问地址

- **智能客服**: <http://localhost:8000>
- **向量库管理**: <http://localhost:5174>

### 环境变量文件 (.env)

```env
# AI API 配置
API_KEY=your_api_key
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL=qwen3.5-flash
EMBEDDING_MODEL=text-embedding-v3

# 向量数据库配置
VECTOR_STORE_PERSIST_DIRECTORY=db/chroma

# 检查点存储配置
CHECKPOINT_STORAGE=memory
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 钉钉智能会话助手

系统已完成钉钉智能会话助手的开发和测试验证。

### 功能特性

- **智能问答**: 基于知识库的智能问答服务
- **日程管理**: 创建、查询、删除钉钉日程
- **待办事项**: 创建钉钉待办任务
- **情绪感知**: 根据用户情绪调整回复语气

### 钉钉部署配置

1. 在钉钉开放平台创建企业内部应用
2. 配置应用密钥（Client ID / Client Secret）
3. 在 `.env` 文件中配置钉钉参数
4. 部署服务并配置钉钉机器人回调地址

```env
# 钉钉配置
DINGTALK_CLIENT_ID=your_app_key
DINGTALK_CLIENT_SECRET=your_app_secret
```

## 功能展示

### Docker 容器化部署

系统已支持 Docker 容器化部署，通过 `docker-compose` 一键启动所有服务：

![Docker 服务架构](resources/docker.png)

### 复杂任务规划

系统支持基于 LLM 的智能任务规划，根据问题难度自动生成多步骤执行计划：

| 难度等级 | 描述        | 任务数量 |
| ---- | --------- | ---- |
| 1级   | 简单事实查询    | 1个任务 |
| 2级   | 需要简单推理    | 1个任务 |
| 3级   | 需要多步骤分析   | 2个任务 |
| 4级   | 需要综合多领域知识 | 3个任务 |
| 5级   | 需要创造性解决方案 | 4个任务 |

### 测试验证截图

#### 核心功能展示

![智能问答与知识库(RAG)、日程管理(MCP)、工具调用与任务规划](resources/drawnix-base.png)

#### 复杂任务规划与执行

![复杂任务规划与执行](resources/drawnix-plan.png)

#### 技能使用（SKILL）

![技能使用展示](resources/drawnix.png)

#### 配置管理界面（支持预览 word excel 等文件）

![配置管理界面](resources/agnet-config.png)
