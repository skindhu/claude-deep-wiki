"""
Structure Prompt Builder - 结构扫描提示词构建器

负责构建所有与结构扫描相关的提示词
"""

import json
from typing import Dict, Any, List


class StructurePromptBuilder:
    """结构扫描的提示词构建器"""

    @staticmethod
    def build_scan_and_identify_prompt(repo_path: str) -> str:
        """
        构建阶段1的提示词：结构扫描与模块识别

        Args:
            repo_path: 仓库根目录路径

        Returns:
            提示词字符串
        """
        return f"""你是代码仓库结构分析专家。这是**阶段1：结构扫描与模块识别**。

仓库路径: {repo_path}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 阶段1 任务：结构扫描与模块识别
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

步骤1: 扫描仓库结构
- **必须**使用 scan_repository_structure 工具扫描仓库（仅调用1次）
- 了解目录结构、文件分布、语言统计

步骤2: 识别业务功能模块
- 基于目录结构和文件命名识别所有业务功能模块
- 构建多级模块层次结构（一级、二级、可选三级）
- 为每个一级模块提供简短职责描述（1-2句话）
  * 基于目录名、文件名推断
  * 不要深入分析代码实现

步骤3: 选择关键文件路径
- 为每个一级模块选择 5-10 个最关键的文件**路径**
- 优先选择：入口文件、管理类、主要业务逻辑文件
- 选择标准：文件名特征（如 index/main/manager/controller）、目录位置
- **注意**：这一阶段只选择路径，不分析文件内容

步骤4: 初步分层判断
- 为每个模块初步判断其层次（core/business/utils）
- 分层标准（基于目录结构和命名）：
  * core: 看起来是基础/通用模块（如 common/core/base）
  * business: 看起来是业务模块（如 user/order/product）
  * utils: 看起来是工具模块（如 helpers/tools/utils）
- **注意**：这只是初步判断，精确分层在阶段3

步骤5: 列出所有文件
- 为每个模块列出所有相关文件路径（完整列表）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 阶段1 约束
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 工具调用：
   - ✅ 使用 scan_repository_structure（1次）
   - ❌ 不要使用 extract_imports_and_exports（留给阶段2）
   - ❌ 不要使用 build_dependency_graph（留给阶段3）

2. 职责边界：
   - ✅ 识别模块结构
   - ✅ 选择关键文件路径
   - ✅ 初步分层判断
   - ❌ 不要分析文件依赖
   - ❌ 不要构建依赖图

3. 描述风格：
   - 职责描述保持简短（1-2句话）
   - 例如："用户认证模块，负责登录注册和权限管理"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 输出格式（必须是完整的 JSON）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

完成分析后，**立即输出一个完整的 JSON 代码块**（用 ```json 包裹）：

```json
{{
  "project_info": {{
    "name": "项目名称",
    "primary_language": "主要编程语言",
    "total_files": 文件总数
  }},
  "modules": [
    {{
      "name": "一级模块名称",
      "layer_guess": "core/business/utils",
      "layer_reason": "初步判断依据",
      "responsibility": "模块简短职责描述（1-2句话）",
      "sub_modules": [
        {{
          "name": "二级模块名称",
          "description": "简短描述"
        }}
      ],
      "all_files": [
        "src/module/file1.js",
        "src/module/file2.js"
      ],
      "key_files_paths": [
        "src/module/main.js",
        "src/module/controller.js"
      ]
    }}
  ]
}}
```

**重要提示**:
- 输出必须是有效的 JSON
- 不要在 JSON 前后添加说明文字
- 确保所有字段都有值（如果某个模块没有子模块，sub_modules 设为空数组 []）
"""

    @staticmethod
    def build_file_dependencies_prompt(
        repo_path: str,
        all_key_files: List[Dict[str, str]]
    ) -> str:
        """
        构建阶段2的提示词：依赖分析

        Args:
            repo_path: 仓库根目录路径
            all_key_files: 所有关键文件列表
                [
                    {"path": "src/module/file.js", "module": "模块名"},
                    ...
                ]

        Returns:
            提示词字符串
        """
        total_files = len(all_key_files)
        files_json = json.dumps(all_key_files, ensure_ascii=False, indent=2)

        return f"""你是代码依赖分析专家。这是**阶段2：依赖分析**。

仓库路径: {repo_path}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 阶段2 任务：分析关键文件依赖
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

你需要分析以下 {total_files} 个关键文件的导入导出关系：

{files_json}

任务步骤:
1. 逐个使用 extract_imports_and_exports 工具分析每个文件
2. **重要**: 文件路径是相对路径时，必须提供 repo_root="{repo_path}" 参数
3. 提取每个文件的：
   - imports: 导入了哪些模块/文件
   - exports: 导出了什么内容
   - language: 文件的编程语言

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 阶段2 约束
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 工具调用：
   - ✅ 使用 extract_imports_and_exports（预算 {total_files} 次）
   - ❌ 不要使用其他工具

2. 职责边界：
   - ✅ 提取导入导出信息
   - ❌ 不要分析模块依赖关系（留给阶段3）
   - ❌ 不要重新判断模块分层（留给阶段3）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 输出格式（必须是完整的 JSON）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

完成分析后，**立即输出一个完整的 JSON 代码块**（用 ```json 包裹）：

```json
{{
  "file_dependencies": [
    {{
      "path": "src/module/main.js",
      "imports": ["vue", "./components/Header", "../utils/helper"],
      "exports": ["default", "init", "AppComponent"],
      "language": "javascript",
      "module": "模块名"
    }}
  ]
}}
```

**重要提示**:
- 如果某个文件分析失败，跳过它，继续分析下一个
- 输出必须是有效的 JSON
- 不要在 JSON 前后添加说明文字
"""

    @staticmethod
    def build_finalize_structure_prompt(
        structure_overview: Dict[str, Any],
        dependencies: Dict[str, Any]
    ) -> str:
        """
        构建阶段3的提示词：综合分析与精确分层

        Args:
            structure_overview: 阶段1的结构概览
            dependencies: 阶段2的依赖信息

        Returns:
            提示词字符串
        """
        overview_json = json.dumps(structure_overview, ensure_ascii=False, indent=2)
        deps_json = json.dumps(dependencies, ensure_ascii=False, indent=2)
        file_deps = dependencies.get('file_dependencies', [])

        return f"""你是代码架构分析专家。这是**阶段3：综合分析与精确分层**。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 阶段3 任务：整合数据并精确分层
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

你有以下数据：

**1. 模块结构概览**:
{overview_json}

**2. 文件依赖信息**:
{deps_json}

任务步骤:
1. 将文件依赖信息整合到各模块的 key_files 中
2. 基于真实的导入导出关系，分析模块间依赖
3. 构建依赖关系图（使用 build_dependency_graph 工具）
4. 基于依赖关系精确判断模块分层：
   - core: 被多个模块依赖的基础模块
   - business: 依赖 core 的业务模块
   - utils: 提供工具功能的模块
5. 生成文件到模块的映射

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 阶段3 约束
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 工具调用：
   - ✅ 可以使用 build_dependency_graph（1次）
   - ❌ 不要重新分析文件

2. 职责边界：
   - ✅ 整合数据
   - ✅ 精确分层
   - ✅ 构建依赖图
   - ✅ 生成映射

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 输出格式（必须是完整的 JSON）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

完成分析后，**立即输出一个完整的 JSON 代码块**（用 ```json 包裹）：

```json
{{
  "project_info": {{
    "name": "项目名称",
    "primary_language": "主要语言",
    "total_files": 文件总数
  }},
  "module_hierarchy": {{
    "modules": [
      {{
        "name": "模块名",
        "layer": "core/business/utils",
        "layer_reason": "精确分层原因（基于依赖关系）",
        "responsibility": "模块职责",
        "sub_modules": [...],
        "all_files": [...],
        "key_files": [
          {{
            "path": "...",
            "imports": [...],
            "exports": [...],
            "language": "..."
          }}
        ]
      }}
    ]
  }},
  "dependency_graph": {{
    "nodes": [
      {{"id": "模块A", "label": "模块A", "layer": "core"}},
      {{"id": "模块B", "label": "模块B", "layer": "business"}}
    ],
    "edges": [
      {{"from": "模块B", "to": "模块A", "relationship": "依赖"}}
    ],
    "mermaid": "graph TD\\n  B[模块B] --> A[模块A]"
  }},
  "file_module_mapping": {{
    "src/module/file1.js": "模块名"
  }},
  "analysis_metadata": {{
    "total_modules": 数字,
    "core_modules": ["..."],
    "business_modules": ["..."],
    "utils_modules": ["..."]
  }}
}}
```

**重要提示**:
- 输出必须是有效的 JSON
- 不要在 JSON 前后添加说明文字
"""

