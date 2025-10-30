# Claude DeepWiki

> 基于 Claude Agent SDK 的智能代码仓库分析工具，自动生成业务导向的项目知识库

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 若希望了解更多AI探索相关的内容，可关注作者公众号

<img src="https://wechat-account-1251781786.cos.ap-guangzhou.myqcloud.com/wechat_account.jpeg" width="30%">

## 📖 项目背景

在 AI 辅助编程时代，**需求质量**成为影响开发效率的关键因素。要让 AI 准确理解需求，首先需要让它掌握项目的背景知识。然而：

- 🔒 **Devin.ai 的 DeepWiki** 效果出色，但闭源且仅支持 GitHub 托管的公开仓库
- 📉 **开源版 open-deepwiki** 分析效果有限，难以满足生产需求

因此，我们基于 **Claude Agent SDK** 打造了这个工具，旨在：
- ✅ 本地运行，支持任何代码仓库（公开/私有）
- ✅ 深度理解业务逻辑，生成面向产品的 PRD 文档
- ✅ 多语言支持（165+ 编程语言）

## 🎯 设计理念

### 1. Claude Agent SDK 驱动

利用 Claude Sonnet 4.5 强大的代码理解能力，通过 Agent SDK 实现自主工具调用和多轮推理。

### 2. 三阶段多 Agent 协作

```
📊 结构扫描 → 🧠 语义分析 → 📄 文档生成
```

**阶段 1: Structure Scanner Agent**
- 扫描项目结构，识别模块层次
- 分析文件依赖关系
- 智能判断模块分层（core/business/utils）

**阶段 2: Semantic Analyzer Agent**
- 概览分析：理解模块的业务价值
- 细节分析：深入挖掘函数/类的业务逻辑（智能分批处理）
- 提取跨文件的业务关系

**阶段 3: Doc Generator Agent**
- 产品功能域智能分组
- 生成业务导向的 PRD 文档
- 质量验证（防止技术术语泄漏）

### 3. MCP 工具标准化

通过 **MCP (Model Context Protocol)** 封装 6 个核心工具：

```python
@tool
def scan_repository_structure(repo_path: str) -> dict:
    """扫描仓库目录结构，识别文件类型和模块组织"""

@tool
def extract_imports_and_exports(file_path: str, language: str) -> dict:
    """提取文件的导入导出关系（基于 Tree-sitter）"""

@tool
def analyze_code_block(code: str, language: str) -> dict:
    """深度分析代码块的 AST 结构和语义"""

@tool
def build_dependency_graph(files_data: list) -> dict:
    """构建模块依赖图"""

@tool
def search_code_patterns(repo_path: str, pattern: str) -> list:
    """搜索特定代码模式（如配置、常量定义）"""

@tool
def validate_analysis_result(analysis: dict) -> dict:
    """验证分析结果的完整性和准确性"""
```

### 4. 核心技术亮点

- **🌐 语言无关**：基于 Tree-sitter 的统一 AST 解析（165+ 语言）
- **🎯 业务视角**：AI 自动提炼技术代码背后的业务价值
- **📦 批处理策略**：智能分批 + token 估算，处理大型项目
- **🔗 精确映射**：每个功能点都关联到具体源码文件
- **🔄 自动重试**：智能检测 JSON 解析错误和分组遗漏，自动重试修正
- **✅ 质量保证**：多重验证机制，防止 AI 幻觉

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Anthropic API Key（Claude Sonnet 4.5）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/claude-deep-wiki.git
cd claude-deep-wiki

# 2. 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key
# 方式1: 环境变量
export ANTHROPIC_API_KEY="your-api-key"

# 方式2: 修改 src/config.py
# ANTHROPIC_AUTH_TOKEN = "your-api-key"
```

> **注意**：`claude-agent-sdk` 目前未发布到 PyPI，如遇到安装问题，请参考 [Claude Agent SDK 文档](https://docs.anthropic.com/en/docs/claude-agent-sdk)

### 运行分析

```bash
# 分析指定代码仓库
python src/main.py /path/to/your/repo
```

### 查看结果

分析完成后，在 `output/` 目录查看结果：

```
output/
├── prd/                          # 产品需求文档
│   ├── Index.md                  # 功能域导航索引
│   ├── 用户认证与授权.md         # 各功能域的详细PRD
│   ├── 订单管理.md
│   └── ...
└── debug/                        # 调试数据（JSON格式）
    ├── 01_structure_scan_final_*.json
    ├── 02_semantic_analysis_final_*.json
    └── ...
```

**PRD 文档结构**：
```markdown
# [功能域名称]

## 1. 功能域概述
- 业务价值
- 核心能力
- 技术架构概览

## 2. 功能详细说明
- 各子功能的业务描述
- 用户场景
- 业务流程

## 3. 跨功能交互
- 与其他功能域的协作关系

## 4. 业务约束与限制
- 业务规则
- 边界条件
```

## 🛠️ 技术栈

| 技术 | 用途 |
|------|------|
| **Claude Agent SDK** | AI 驱动的多 Agent 协作框架 |
| **Tree-sitter** | 165+ 编程语言的统一 AST 解析 |
| **MCP** | 工具调用的标准化协议 |
| **Python 3.11+** | 主要开发语言 |

## 📁 项目结构

```
claude-deep-wiki/
├── src/
│   ├── agents/                   # 三个分析 Agent
│   │   ├── structure_scanner_agent.py
│   │   ├── semantic_analyzer_agent.py
│   │   └── doc_generator_agent.py
│   ├── mcp_servers/              # MCP 工具服务器
│   │   └── code_analysis_server.py
│   ├── mcp_tools/                # 底层分析工具
│   │   ├── polyglot_parser.py   # Tree-sitter 解析器
│   │   ├── dependency_analyzer.py
│   │   ├── language_detector.py
│   │   └── ...
│   ├── utils/                    # 辅助工具
│   │   ├── claude_query_helper.py  # Claude查询助手（带重试）
│   │   ├── batch_analyzer.py    # 批处理管理
│   │   ├── json_extractor.py    # JSON 提取
│   │   └── *_prompt_builder.py  # 提示词构建
│   ├── config.py                 # 配置文件
│   └── main.py                   # 主入口
├── output/                       # 输出目录
├── requirements.txt              # Python 依赖
└── README.md                     # 项目文档
```

## 🎓 核心设计思想

### 防止 AI 幻觉

1. **分阶段处理**：每个阶段独立验证，避免错误累积
2. **工具驱动**：AI 通过工具获取真实数据，而非凭空想象
3. **智能重试**：自动检测 JSON 解析错误、模块遗漏等问题，最多重试 3 次
4. **质量检查**：自动验证输出中是否包含不合规内容（如技术术语）

### 鲁棒性设计

- **统一查询接口**：`ClaudeQueryHelper` 封装所有 Claude API 调用，集中处理错误
- **自动错误恢复**：
  - JSON 语法错误：自动重试，给 Claude 第二次机会
  - 模块分组遗漏：验证器检测后触发重试，确保完整性
  - 字段缺失：验证器实时检查，避免后续流程失败
- **详细日志**：记录每次重试的原因，便于问题排查

### Session 管理策略

- **StructureScannerAgent**：每个子阶段独立 session（显式传递数据）
- **SemanticAnalyzerAgent**：同一模块共享 session（保持上下文理解）
- **DocGeneratorAgent**：按功能域独立 session（避免混淆）

### 批处理优化

- Token 估算：根据文件内容预估 token 消耗
- 内聚性分组：将相关文件分到同一批次
- 动态调整：根据实际响应调整批次大小

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

[MIT License](LICENSE)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**

