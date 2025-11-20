"""
Structure Prompt Builder - 结构扫描提示词构建器

负责构建所有与结构扫描相关的提示词
"""

import json
from typing import Dict, Any, List, Optional


class StructurePromptBuilder:
    """结构扫描的提示词构建器"""

    @staticmethod
    def build_orphan_files_fix_prompt(
        modules: List[Dict[str, Any]],
        orphan_files: List[Dict[str, Any]],
        repo_path: str
    ) -> str:
        """
        构建孤立文件修复提示词

        Args:
            modules: 现有模块列表
            orphan_files: 孤立文件列表
            repo_path: 仓库路径

        Returns:
            提示词字符串
        """
        # 构建模块摘要（显示所有模块）
        modules_summary = []
        for module in modules:
            modules_summary.append({
                "name": module.get('name'),
                "responsibility": module.get('responsibility'),
                "file_count": len(module.get('all_files', [])),
                "sample_files": module.get('all_files', [])[:3]  # 示例文件
            })

        modules_json = json.dumps(modules_summary, ensure_ascii=False, indent=2)

        # 构建孤立文件列表（只保留路径和语言信息，减少 token）
        orphan_summary = []
        for file_info in orphan_files:
            orphan_summary.append({
                "path": file_info.get('path'),
                "language": file_info.get('language')
            })

        orphan_json = json.dumps(orphan_summary, ensure_ascii=False, indent=2)

        return f"""你是代码仓库结构分析专家。需要处理一些未被分类的孤立文件。

⚠️ 重要限制：
- **不要调用任何工具**（如 read_code_files）
- **仅根据文件路径和文件名进行分类判断**
- **立即输出 JSON，不要先做分析说明**

仓库路径: {repo_path}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 任务：孤立文件智能归类
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 现有模块列表

{modules_json}

## 需要归类的孤立文件

{orphan_files}个文件需要归类：

{orphan_json}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 归类规则
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

为每个孤立文件选择最合适的处理方式：

### 选项1: assign_to_existing（分配到现有模块）
- 如果文件在语义上属于某个现有模块
- 例如：测试文件归入对应的业务模块

### 选项2: create_new_module（创建新模块）
- 如果多个孤立文件属于同一个新的功能域
- 例如：文档文件、CI配置文件、部署脚本等
- 新模块必须包含：
  * name: 模块名称
  * layer_guess: core/business/utils
  * responsibility: 职责描述
  * all_files: 包含的文件列表
  * key_files_paths: 关键文件（可以为空）
  * sub_modules: 子模块（通常为空）

### 选项3: assign_to_other（归入"其他文件"）
- 如果文件确实无法归类
- 例如：零散的配置文件、临时文件等

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 注意事项
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 优先考虑分配到现有模块（选项1）
2. 只在确实需要时创建新模块（选项2）
3. "其他文件"模块是最后的选择（选项3）
4. 每个决策都要提供清晰的理由
5. 相关的文件应该归入同一个模块

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 输出格式（必须是完整的 JSON）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```json
{{
  "assignments": [
    {{
      "file": "文件路径",
      "action": "assign_to_existing",
      "target_module": "模块名",
      "reason": "归类理由"
    }},
    {{
      "file": "文件路径",
      "action": "create_new_module",
      "new_module": {{
        "name": "新模块名",
        "layer_guess": "utils",
        "responsibility": "模块职责",
        "all_files": ["该模块包含的所有孤立文件"],
        "key_files_paths": [],
        "sub_modules": []
      }},
      "reason": "创建理由"
    }},
    {{
      "file": "文件路径",
      "action": "assign_to_other",
      "reason": "无法归类的原因"
    }}
  ]
}}
```

**重要约束**：
- ❌ 不要调用任何工具（read_code_files、grep 等）
- ✅ 仅根据文件路径、文件名和语言信息进行判断
- ✅ 每个孤立文件都必须有一个分配决策
- ✅ 如果创建新模块，确保将所有相关文件都包含在 new_module.all_files 中
- ✅ action 必须是: assign_to_existing, create_new_module, assign_to_other 之一
- ✅ 输出必须是有效的 JSON，不要有额外说明文字
- ✅ 直接输出 JSON，不要先进行分析或解释

现在请立即输出完整的 JSON：
"""

    @staticmethod
    def build_scan_and_identify_prompt(
        repo_path: str,
        predefined_modules_content: Optional[str] = None
    ) -> str:
        """
        构建阶段1的提示词：一级模块识别与职责总结

        识别顶层模块，基于关键文件的语义理解总结模块职责。
        不细分子模块，子模块细分在阶段3进行。

        Args:
            repo_path: 仓库根目录路径
            predefined_modules_content: 可选的预定义一级模块信息（字符串格式，可以是JSON、Markdown、纯文本等）

        Returns:
            提示词字符串
        """

        # 构建模块定义部分
        if predefined_modules_content:
            module_definition_section = f"""
步骤2: 使用预定义的一级产品模块
以下是预定义的一级产品模块信息：

```
{predefined_modules_content}
```

⚠️ **重要**：
- ✅ **必须使用**上述预定义的模块结构
- ✅ 按照预定义的模块名称、目录路径来组织文件
- ✅ 将扫描结果中的文件按照预定义模块的目录路径分配到对应模块
- ⚠️ **不要在此阶段细分子模块**
  * 所有文件都归属到一级产品模块的 all_files 中
  * 不需要 sub_modules 字段
- ⚠️ 如果有文件不属于任何预定义模块，可以创建"其他文件"模块
"""
        else:
            module_definition_section = """
步骤2: 识别一级产品模块
- 基于目录结构和文件命名识别所有**一级产品模块**（顶层模块）
- 典型的一级产品模块包括：
  * 应用模块（app_*/apps/*）
  * 业务模块（modules/*）
  * 基础库（libs/*）
  * 平台配置（android/、ios/）
  * 工具模块（plugins/、tools/）
- ⚠️ **不要在此阶段细分子模块**
  * 所有文件都归属到一级产品模块的 all_files 中
  * 不需要 sub_modules 字段
"""

        return f"""你是代码仓库结构分析专家。这是**阶段1：一级模块识别与职责总结**。

仓库路径: {repo_path}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 阶段1 任务：识别顶层模块（不细分子模块）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **本阶段目标**：
- ✅ 识别所有一级模块（顶层模块）
- ✅ 为每个模块选择关键文件，并基于其内容总结模块职责
- ❌ 不要细分子模块（子模块细分在阶段3进行）

步骤1: 扫描仓库结构
- **必须**使用 scan_repository_structure 工具扫描仓库（仅调用1次）
- 了解目录结构、文件分布、语言统计
{module_definition_section}

步骤3: 选择关键文件并进行语义分析 ⭐ 核心步骤
- 为每个一级产品模块选择 5-10 个最关键的文件路径
  * 优先选择：
    - 入口文件（main.dart, index.js, app.py）
    - 管理类/控制器（*_manager.*, *_controller.*）
    - 主要业务逻辑文件（根目录下的核心文件）
    - 配置文件（pubspec.yaml, package.json, build.gradle）
  * 选择标准：文件名特征、目录位置、文件大小

- **使用 read_code_files 工具**读取这些关键文件的内容（批量读取）

- 基于文件内容进行**语义理解**：
  * 提取主要类名、函数名、接口定义
  * 阅读文件顶部注释和文档字符串
  * 观察 import/export 语句，了解模块对外暴露的能力
  * 识别业务术语（如 user/order/payment 等）

- ⭐ **为每个模块生成 responsibility 字段**（基于语义理解）：
  * 描述应准确反映模块的真实业务功能
  * 长度：1-2 句话
  * 格式："[模块作用]，提供[核心能力1]、[核心能力2]等功能"
  * 示例：
    - "用户管理模块，提供用户注册、登录、权限控制、个人信息管理等功能"
    - "基础通用库，提供网络请求、数据存储、工具类、扩展函数等底层能力"
  * ⚠️ 不要猜测，必须基于关键文件的实际内容

步骤4: 初步分层判断
- 为每个模块初步判断其层次（core/business/utils）
- 分层标准（综合目录结构、命名和步骤3的语义理解）：
  * core: 基础/通用模块（如 lib_base_common, common），提供底层能力
  * business: 业务模块（如 user_module, order_module），实现具体业务功能
  * utils: 工具模块（如 debug_module, plugins），提供辅助功能
- **注意**：这只是初步判断，精确分层在后续阶段

步骤5: 定义文件匹配模式（⚠️ 完整性要求）
- **必须**为每个一级模块定义**文件匹配模式**（glob 通配符）
- **关键要求**：确保扫描结果中的每个文件都能被某个模块的 patterns 匹配到
  * 需要匹配的文件类型：
    - 源码文件（category == 'source'）：.py, .js, .ts, .java, .go, .dart, .swift, .rb, .h 等
  * 无需匹配的文件类型（自动忽略）：
    - 文档（.md, .rst）、Web 资源（.html, .css）、图片等

- **Glob 通配符规则**：
  * `**` 表示匹配任意层级的目录
  * `*` 表示匹配任意字符（不包括路径分隔符）
  * 示例：
    - `app_cf/**/*.dart` - 匹配 app_cf 目录下所有 dart 文件
    - `lib/user/**/*` - 匹配 lib/user 目录下所有文件
    - `android/**/*.java` - 匹配 android 目录下所有 java 文件
  * ⚠️ **不要使用正则表达式**，只使用 glob 通配符

- **模式设计原则**：
  * 每个模块 3-10 条 patterns 即可覆盖所有文件
  * 按文件类型或子目录分组（如 `app_cf/**/*.dart`, `app_cf/**/*.swift`）
  * 确保 patterns 能覆盖模块的所有文件

- 平台特定文件也必须匹配：
  * iOS 文件：可创建 `ios/**/*` 等 pattern
  * Android 文件：可创建 `android/**/*` 等 pattern
  * 可以创建"iOS 平台配置"、"Android 平台配置"等模块

- 如果有文件无法明确归类，必须创建"其他文件"或"配置管理"模块
- ⚠️ **绝对不允许遗漏任何文件**

步骤6: 输出 JSON

完成分析后，立即输出完整的 JSON（见下方格式）

步骤7: 自我验证（⚠️ 必须执行）

输出 JSON 后，**立即使用 validate_structure_completeness 工具进行验证**：

```
validate_structure_completeness(
    repo_path="{repo_path}",
    structure_overview=<刚才输出的JSON对象>
)
```

- 如果验证通过 (valid: true)：完成任务
- 如果验证失败 (valid: false)：
  * 查看 issues 和 recommendations
  * 根据 orphan_files 列表，将遗漏的文件补充到相应模块
  * 重新输出完整的 JSON
  * 再次调用验证工具确认

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 阶段1 约束
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 工具调用：
    - ✅ 必须使用 scan_repository_structure（1次）- 扫描仓库结构
   - ✅ 必须使用 read_code_files（多次）- 读取关键文件内容
   - ✅ 必须使用 validate_structure_completeness（至少1次）- 验证完整性
   - ❌ 不要使用 extract_imports_and_exports（留给阶段3）
   - ❌ 不要使用 build_dependency_graph（留给阶段3）

2. 职责边界：
   - ✅ 识别一级模块结构
   - ✅ 选择关键文件路径并读取内容
   - ✅ 基于关键文件语义理解总结模块职责
   - ✅ 初步分层判断
   - ❌ 不要细分子模块（留给阶段3）
   - ❌ 不要分析文件依赖
   - ❌ 不要构建依赖图

3. 描述风格：
   - responsibility 必须基于关键文件的实际内容
   - 长度：1-2句话
   - 例如："用户认证模块，提供登录注册、权限管理、会话管理等功能"

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
      "responsibility": "基于关键文件语义理解的职责描述（1-2句话）",
      "all_files_patterns": [
        "module_name/**/*.dart",
        "module_name/**/*.swift",
        "module_name/**/*.java"
      ],
      "key_files_paths": [
        "path/to/main.js",
        "path/to/manager.js"
      ]
    }},
    {{
      "name": "另一个一级模块",
      "layer_guess": "business",
      "layer_reason": "初步判断依据",
      "responsibility": "基于关键文件语义理解的职责描述（1-2句话）",
      "all_files_patterns": [
        "other_module/**/*"
      ],
      "key_files_paths": [
        "path/to/index.js"
      ]
    }}
  ]
}}
```

**重要提示**:
- ⚠️ **必须包含 responsibility 字段**：基于关键文件的语义理解总结模块职责
- ⚠️ **必须包含 all_files_patterns 字段**：使用 glob 通配符定义文件匹配模式
- ⚠️ **不要包含 all_files 字段**：避免 token 超限，使用 patterns 代替
- ⚠️ **不要包含 sub_modules 字段**：阶段1只识别一级模块
- ⚠️ **不要使用正则表达式**：只使用 glob 通配符（`**`, `*`）
- 输出必须是有效的 JSON
- 不要在 JSON 前后添加说明文字
- 确保所有字段都有值
- 每个模块 3-10 条 patterns 即可
- ⚠️ **确保覆盖完整性**：所有源码文件都能被某个模块的 patterns 匹配到
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

    @staticmethod
    def build_module_subdivision_planning_prompt(
        module_info: Dict[str, Any],
        repo_path: str
    ) -> str:
        """
        构建阶段3.1的提示词：大模块细分规划

        规划子模块结构，建议关键文件和入口文件。
        文件分配在阶段3.2通过依赖分析自动完成

        Args:
            module_info: 大模块信息（包含 name, responsibility, all_files, key_files_paths）
            repo_path: 仓库根路径

        Returns:
            提示词字符串
        """
        module_name = module_info['module_name']
        responsibility = module_info['module_ref'].get('responsibility', '未知职责')
        total_files = len(module_info['all_files'])

        # 按目录分组文件，提供目录结构视图
        from collections import defaultdict
        dir_structure = defaultdict(list)
        for file_path in module_info['all_files']:
            dir_name = '/'.join(file_path.split('/')[:-1]) or '根目录'
            file_name = file_path.split('/')[-1]
            dir_structure[dir_name].append(file_name)

        # 构建目录结构展示（每个目录显示前10个文件作为示例）
        dir_structure_lines = []
        for dir_name, files in sorted(dir_structure.items()):
            file_count = len(files)
            display_files = files[:10]  # 显示前10个作为示例，完整列表在后面提供
            remaining = file_count - len(display_files)

            dir_structure_lines.append(f"  📁 {dir_name}/ ({file_count} 个文件)")
            for file_name in display_files:
                dir_structure_lines.append(f"     - {file_name}")
            if remaining > 0:
                dir_structure_lines.append(f"     ... 还有 {remaining} 个文件")

        dir_structure_text = '\n'.join(dir_structure_lines)

        # 关键文件信息
        key_files = module_info['module_ref'].get('key_files_paths', [])
        key_files_json = json.dumps(key_files, ensure_ascii=False, indent=2)

        # 获取模块的 all_files_patterns（如果有）
        all_files_patterns = module_info['module_ref'].get('all_files_patterns', [])
        patterns_json = json.dumps(all_files_patterns, ensure_ascii=False, indent=2) if all_files_patterns else None

        return f"""你是代码结构分析专家。这是**阶段3.1：大模块细分规划**。

仓库路径: {repo_path}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 任务：规划子模块结构（只规划，不分配文件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 待细分的大模块

- **模块名称**: {module_name}
- **模块职责**: {responsibility}
- **文件总数**: {total_files} 个文件
- **任务**: 将此大模块按**产品功能**细分为多个子模块
- **⚠️ 重要**: 子模块需要尽量细致，每个子模块应该是一个清晰、独立、小粒度的产品功能单元

## 目录结构概览（快速浏览，每个目录仅显示前10个文件）

{dir_structure_text}

## 一级模块的关键文件（参考）

{key_files_json}

## 📋 如何查询模块的完整文件列表

该模块包含 {total_files} 个文件。为了避免 prompt 过长，文件列表未直接提供。

**你可以使用 filter_files_by_patterns 工具查询文件**：

```
filter_files_by_patterns(
    repo_path="{repo_path}",
    patterns={patterns_json if patterns_json else '["模块目录/**/*"]'}
)
```

⚠️ **使用建议**：
- 在规划子模块前，可以先调用此工具了解模块的完整文件列表
- 根据目录结构和文件名识别子功能
- 建议关键文件时，确保文件路径真实存在（可通过工具验证）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 规划要求
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **本阶段目标**：只规划子模块，不分配所有文件
- ✅ **必须使用 filter_files_by_patterns 工具**获取模块完整文件列表
- ✅ 识别子模块（产品功能维度）
- ✅ **追求细粒度**：子模块应该尽可能小而聚焦，宁多勿少
- ✅ 为每个子模块**建议** suggested_key_files（2-10个，根据子模块大小）
- ✅ 为每个子模块**建议** suggested_entry_files（1-3个）
- ❌ **不要**在此阶段分配所有文件（all_files 将在阶段3.2自动生成）

### 规划步骤

1. **查询完整文件列表**（⚠️ 必需）：
   - **必须使用 filter_files_by_patterns 工具**获取模块的完整文件列表
   - 了解模块包含哪些文件，按目录和文件名识别功能
   - 这比只看"目录结构概览"更全面（因为概览只显示前10个文件）
   - ⚠️ 不调用此工具将无法全面了解模块结构，可能导致子模块划分不准确

2. **分析目录结构**：
   - 查看"目录结构概览"和完整文件列表
   - 根据目录名称和文件名识别可能的产品功能模块
   - 例如：`user_profile/` → "用户资料管理功能"
   - 例如：`order_management/` → "订单管理功能"

3. **阅读关键文件**（⚠️ 必需）：
   - **必须使用 read_code_files 工具**读取一级模块的关键文件
   - 了解模块的实际功能和业务逻辑
   - 基于文件内容而非猜测来规划子模块
   - 建议读取 5-10 个最关键的文件

4. **规划子模块**（⚠️ 尽量细致）：
   - **细粒度原则**：每个子模块应该是一个清晰、独立、小粒度的产品功能单元
   - **数量要求**：
     * 如果模块较小（<50 文件）：建议 5-15 个子模块
     * 如果模块中等（50-200 文件）：建议 10-30 个子模块
     * 如果模块较大（>200 文件）：建议 20-50 个子模块
     * ⚠️ 不要害怕子模块过多，细致的划分有助于理解代码结构

   - **划分示例**（细粒度）：
     * ✅ 好的细分："用户注册"、"用户登录"、"用户密码重置"、"用户资料编辑"
     * ❌ 粗糙的划分："用户管理"（太宽泛，应该拆分成多个子功能）
     * ✅ 好的细分："商品列表展示"、"商品详情页"、"商品搜索"、"商品筛选"
     * ❌ 粗糙的划分："商品功能"（太宽泛，应该拆分）

   - **命名和描述**：
     * 为每个子模块命名（体现具体的产品功能点）
     * 撰写简短描述（1-2句话，说明该子功能的具体作用）

5. **关键文件和入口文件**：
   - ⚠️ **建议文件路径时，使用 filter_files_by_patterns 工具查询验证**（确保文件真实存在）
   - `suggested_key_files`: 该功能的核心文件（2-10个，根据子模块大小调整）
     * 优先选择：管理类、控制器、主页面、核心业务逻辑文件
     * 必须是完整路径（如 `src/modules/user/profile/profile_page.dart`）
     * 细粒度子模块可以只有 2-5 个关键文件
   - `suggested_entry_files`: 该功能的入口文件（1-3个）
     * 优先选择：路由入口、主页面、index文件
     * 必须是完整路径（如 `src/modules/user/user_routes.dart`）
   - ⚠️ 这些文件将在阶段3.2用于依赖分析，自动找出所有关联文件

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 关键约束
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **工具调用要求**（⚠️ 必须执行）:
   - ✅ **必须调用 filter_files_by_patterns 工具**获取模块的完整文件列表
   - ✅ 必须调用 read_code_files 工具阅读关键文件内容
   - ❌ 不要基于猜测规划子模块，必须基于实际文件内容
   - ❌ 不要跳过工具调用直接输出结果

2. **子模块粒度**（⚠️ 重中之重）:
   - ✅ **细粒度优先**：每个子模块应该尽可能小而聚焦
   - ✅ 每个子模块是一个具体的、独立的产品功能点（而非功能类别）
   - ✅ 子模块之间相互独立（低耦合）
   - ✅ 宁可多划分，不可少划分（细致的划分更有利于代码理解）
   - ❌ 不要按技术分层（如 models/views/controllers）
   - ❌ 避免创建过于宽泛的子模块（如"用户管理"应拆分为"用户注册"、"用户登录"等）

3. **命名规范**:
   - ✅ 名称体现具体的产品功能点（如 "用户注册"、"用户登录" 而非 "用户管理"）
   - ✅ description 简短描述（1-2句话，说明该功能的具体作用）
   - ✅ 优先使用动宾结构（如 "编辑用户资料"、"展示商品列表"）

4. **文件建议**:
   - ✅ suggested_key_files 和 suggested_entry_files 必须是实际存在的文件路径
   - ✅ 这些文件路径必须从"完整文件列表"中选择
   - ✅ 必须是完整路径（包含所有目录层级）
   - ✅ 对于细粒度的子模块，suggested_key_files 可以是 2-5 个文件（不必强求 5-10 个）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 输出格式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```json
{{
  "sub_modules": [
    {{
      "name": "用户注册",
      "description": "提供用户注册功能，包括手机号注册、邮箱注册、第三方账号绑定等",
      "suggested_key_files": [
        "path/to/register_page.dart",
        "path/to/register_controller.dart"
      ],
      "suggested_entry_files": [
        "path/to/register_page.dart"
      ]
    }},
    {{
      "name": "用户登录",
      "description": "提供用户登录功能，包括账号密码登录、短信验证码登录、第三方登录等",
      "suggested_key_files": [
        "path/to/login_page.dart",
        "path/to/login_controller.dart"
      ],
      "suggested_entry_files": [
        "path/to/login_page.dart"
      ]
    }},
    {{
      "name": "密码重置",
      "description": "提供密码重置功能，支持通过手机号或邮箱找回密码",
      "suggested_key_files": [
        "path/to/reset_password_page.dart"
      ],
      "suggested_entry_files": [
        "path/to/reset_password_page.dart"
      ]
    }},
    {{
      "name": "用户资料编辑",
      "description": "提供用户资料编辑功能，包括头像、昵称、个人简介等信息的修改",
      "suggested_key_files": [
        "path/to/profile_edit_page.dart"
      ],
      "suggested_entry_files": [
        "path/to/profile_edit_page.dart"
      ]
    }}
  ]
}}
```

**示例说明**:
上述示例展示了细粒度的子模块划分：将"用户管理"拆分为"用户注册"、"用户登录"、"密码重置"、"用户资料编辑"等具体功能点。

**重要**:
- ⚠️ **必须先调用工具**：在输出 JSON 前，必须先调用 filter_files_by_patterns 和 read_code_files 工具
- ⚠️ **追求细粒度**：子模块数量宁多勿少，每个子模块应该是一个具体的、小的功能点
- ❌ **不要包含 all_files 字段**（将在阶段3.2自动生成）
- ✅ 输出必须是有效的 JSON
- ✅ 所有文件路径必须真实存在
- ✅ 对于细粒度子模块，suggested_key_files 可以只有 2-5 个文件

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 开始规划前的检查清单
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在输出 JSON 前，请确认你已完成：
- [ ] 调用 filter_files_by_patterns 工具获取完整文件列表
- [ ] 调用 read_code_files 工具阅读关键文件
- [ ] 基于文件内容（非猜测）规划子模块

完成上述步骤后，请输出完整的 JSON：
"""