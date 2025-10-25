"""
PRD Prompt Builder - PRD文档生成提示词构建器

负责构建所有与PRD文档生成相关的提示词
"""

import json
from typing import Dict, Any, List


class PRDPromptBuilder:
    """PRD文档生成的提示词构建器"""

    @staticmethod
    def build_product_grouping_prompt(modules_summary: List[Dict[str, Any]]) -> str:
        """
        构建产品功能域分组提示词

        Args:
            modules_summary: 所有技术模块的摘要信息
                [
                    {
                        "module_name": "assets",
                        "business_purpose": "...",
                        "core_features": [...]
                    }
                ]

        Returns:
            提示词字符串
        """
        modules_json = json.dumps(modules_summary, ensure_ascii=False, indent=2)

        prompt = f"""你是一位资深的产品经理，需要将技术模块重新组织为产品功能域。

# 任务目标
分析以下技术模块的业务价值，将它们按照产品功能域进行智能分组。

# 技术模块信息
{modules_json}

# 分组原则
1. **按业务价值和用户视角分组**，不是按技术架构
2. **每个功能域应该对应一个独立的产品能力**（用户可感知、可独立使用）
3. **功能域数量由项目规模和业务复杂度决定**：
   - 不设置硬性数量限制
   - 小项目可能只有 2-3 个功能域
   - 大型项目可能有 10+ 个功能域
   - 关键判断标准：业务独立性和职责边界
4. **功能域划分的核心标准**：
   - 业务职责是否独立清晰
   - 用户是否能独立感知和使用
   - 功能域之间耦合度是否低
   - **充分考虑模块间的交互关系**：频繁交互的模块往往属于同一功能域
   - 避免过度拆分（太细碎，失去完整性）
   - 避免过度聚合（太笼统，失去独立性）
5. **技术模块可以被多个功能域复用**：
   - 核心业务模块通常归属一个功能域
   - 基础设施/工具类模块可以被多个功能域共同使用
   - 如果一个模块被多个功能域依赖，可在多个功能域中列出
6. **支持功能域层级结构**（适应大型项目）：
   - 如果某个功能域包含的技术模块过多（建议 > 8个），应考虑划分二级子域
   - 二级子域也要有清晰的业务边界和产品语义
   - 层级深度建议不超过2级（一级功能域 + 二级子域）
7. **功能域命名要面向产品/业务**，不要使用技术术语

# 分组示例

**示例1 - 核心业务模块（单一归属）**:
技术模块：`components`, `otherPages`, `entry`
→ 功能域：**用户交互与界面** - 负责所有用户可见的界面展示和交互操作

**示例2 - 基础设施模块（多域复用）**:
技术模块：`js/common`（包含工具函数、错误处理等）
→ 可以同时出现在多个功能域：
  - **用户交互与界面**（使用其工具函数）
  - **数据服务层**（使用其错误处理）
  - **导航与追踪**（使用其日志工具）

**示例3 - 混合场景**:
- `js/router` → **导航与用户体验**（核心功能）
- `js/services` → **数据服务层**（核心功能）
- `js/log` → 可出现在多个功能域（被广泛依赖的基础能力）

**示例4 - 层级结构（大型功能域）**:
```json
{{
  "domain_name": "数据服务层",
  "domain_description": "提供全面的数据获取、处理和存储能力",
  "business_value": "确保数据的准确性和及时性",
  "technical_modules": [],  // 因为有子域，所以一级为空
  "sub_domains": [
    {{
      "sub_domain_name": "用户数据服务",
      "sub_domain_description": "管理用户相关的数据操作",
      "technical_modules": ["user-service", "user-cache", "user-validator"]
    }},
    {{
      "sub_domain_name": "业务数据服务",
      "sub_domain_description": "处理核心业务数据",
      "technical_modules": ["order-service", "payment-service", "inventory-service"]
    }}
  ]
}}
```

# 输出要求
请以 JSON 格式返回分组结果，必须严格遵循以下结构：

```json
{{
  "product_domains": [
    {{
      "domain_name": "功能域名称（面向产品，如：用户交互与界面）",
      "domain_description": "该功能域的业务定位和职责描述（1-2句话）",
      "business_value": "该功能域为用户/业务带来的核心价值（1句话）",
      "technical_modules": ["技术模块名1", "技术模块名2"],
      "sub_domains": [
        {{
          "sub_domain_name": "二级子域名称（可选，仅在模块数量>8时使用）",
          "sub_domain_description": "子域的业务定位",
          "technical_modules": ["该子域包含的技术模块"]
        }}
      ]
    }}
  ]
}}
```

**层级结构说明**：
- 如果一级功能域包含的技术模块 ≤ 8个，直接在 `technical_modules` 中列出，`sub_domains` 为空数组
- 如果一级功能域包含的技术模块 > 8个，应在 `sub_domains` 中进一步划分二级子域
- 二级子域划分后，一级功能域的 `technical_modules` 应为空（所有模块归属到子域中）
- 基础设施/工具类模块如果被多个功能域使用，可以在多个功能域的 `technical_modules` 中出现

# 注意事项
- **所有字段内容必须使用中文**（domain_name, domain_description, business_value 等）
- 确保所有技术模块都被分配到至少一个功能域
- 不要遗漏任何模块
- 基础设施类模块可以出现在多个功能域中，这是正常的
- domain_name 必须简洁且具有产品语义
- 输出必须是纯 JSON 格式，不要有任何额外说明文字
"""
        return prompt

    @staticmethod
    def build_domain_prd_prompt(
        domain_info: Dict[str, Any],
        aggregated_modules_data: List[Dict[str, Any]],
        repo_path: str
    ) -> str:
        """
        构建产品功能域PRD生成提示词

        Args:
            domain_info: 功能域信息
                {
                    "domain_name": "...",
                    "domain_description": "...",
                    "business_value": "...",
                    "sub_domains": [...]  # 可选的二级子域
                }
            aggregated_modules_data: 该功能域下所有技术模块的完整数据
                [
                    {
                        "module_name": "...",
                        "overview": {...},
                        "detailed_analysis": {...}
                    }
                ]
            repo_path: 仓库路径

        Returns:
            PRD生成提示词
        """
        domain_name = domain_info.get('domain_name', '未命名功能域')
        domain_description = domain_info.get('domain_description', '')
        business_value = domain_info.get('business_value', '')
        sub_domains = domain_info.get('sub_domains', [])

        # 保持模块数据完整（分批生成会处理token限制）
        detailed_modules = []
        for module_data in aggregated_modules_data:
            module_name = module_data.get('module_name', '')
            overview = module_data.get('overview', {})
            detailed = module_data.get('detailed_analysis', {})

            detailed_modules.append({
                'module_name': module_name,
                'business_purpose': overview.get('business_purpose', ''),
                'core_features': overview.get('core_features', []),
                'external_interactions': overview.get('external_interactions', []),
                'files_analysis': detailed.get('files_analysis', [])  # ✅ 保持完整，不截断
            })

        modules_json = json.dumps(detailed_modules, ensure_ascii=False, indent=2)

        # 准备子域信息
        sub_domains_info = ""
        if sub_domains:
            sub_domains_info = "\n\n# 功能域层级结构\n该功能域包含以下二级子域：\n"
            for i, sub in enumerate(sub_domains, 1):
                sub_domains_info += f"{i}. **{sub.get('sub_domain_name', '')}**\n"
                sub_domains_info += f"   - 定位：{sub.get('sub_domain_description', '')}\n"
                sub_domains_info += f"   - 包含模块：{', '.join(sub.get('technical_modules', []))}\n"

        prompt = f"""你是一位资深的产品经理，需要为产品功能域编写详细的产品需求文档（PRD）。

# 项目信息
- **项目路径**: {repo_path}

# 功能域信息
- **功能域名称**: {domain_name}
- **功能域定位**: {domain_description}
- **业务价值**: {business_value}
{sub_domains_info}
# 技术实现模块
以下是该功能域包含的技术模块及其业务逻辑分析结果：

{modules_json}

# PRD 编写要求

{PRDPromptBuilder._get_language_style_requirements()}

{PRDPromptBuilder._get_document_structure_requirements(include_subdomain_guide=True)}

{PRDPromptBuilder._get_content_quality_requirements()}

{PRDPromptBuilder._get_function_description_format()}

{PRDPromptBuilder._get_diagram_usage_principles()}

{PRDPromptBuilder._get_output_format_requirement(full_document=True)}
"""
        return prompt

    @staticmethod
    def build_index_prompt(all_domains_info: List[Dict[str, Any]], repo_path: str) -> str:
        """
        构建导航索引生成提示词

        Args:
            all_domains_info: 所有产品功能域的概览信息
                [
                    {
                        "domain_name": "...",
                        "domain_description": "...",
                        "business_value": "...",
                        "prd_file": "xxx.md"
                    }
                ]
            repo_path: 仓库路径

        Returns:
            生成 Index.md 的提示词
        """
        domains_json = json.dumps(all_domains_info, ensure_ascii=False, indent=2)

        prompt = f"""你是一位资深的产品经理，需要为产品需求文档集合编写完整的索引汇总。

# 项目路径
{repo_path}

# 产品功能域列表
{domains_json}

# 任务要求
生成一个 Index.md 文件，**直接包含所有功能域的完整信息**，而不是链接到其他文档。
这是一个独立的、完整的产品功能索引，用户只需要阅读这一个文件就能了解所有功能域。

# 文档结构

## 第1部分：项目概览
- 简要介绍这个项目是做什么的（基于各功能域推断整体产品定位）
- 说明产品的核心价值和目标用户群体
- 列出产品的主要功能领域（即各个产品功能域）

## 第2部分：产品功能域详情
**重要**：直接在此展示每个功能域的详细信息，不要使用链接。

对每个功能域按以下格式展示：

### 功能域X：[功能域名称]

#### 功能定位
[该功能域的业务定位和职责描述]

#### 业务价值
[该功能域为用户/业务带来的核心价值]

#### 核心能力
- 能力1：[简要描述]
- 能力2：[简要描述]
- 能力3：[简要描述]
...

#### 关联的技术模块
[列出该功能域包含的技术模块名称]

---

（重复以上格式，展示所有功能域）

## 第3部分：功能域关系说明（可选）
如果功能域之间有明显的协作关系，可以简要说明。

# 输出要求
- **必须使用中文**输出所有内容
- 使用 Markdown 格式
- **不要使用任何链接或引用外部文档**
- 直接在本文件中展示所有功能域的完整信息
- 语言风格要专业、清晰
- 使用产品语言，不要有技术术语
- 直接输出文档内容，不要有任何前置说明或元信息
"""
        return prompt

    @staticmethod
    def _get_language_style_requirements() -> str:
        """获取语言风格要求"""
        return """## 语言风格要求
- **严格禁止使用技术术语**，必须使用产品语言：
  - ❌ 禁止：function, method, class, object, API, endpoint, parameter, return value, throw, catch, query, interface, component
  - ✅ 使用：功能、操作、业务实体、数据、系统交互、接口、输入项、输出结果、异常情况、数据获取
- 面向产品和业务人员，假设读者不懂代码
- 描述"用户能做什么"，而不是"系统如何实现"
"""

    @staticmethod
    def _get_content_quality_requirements() -> str:
        """获取内容质量要求"""
        return """## 内容质量要求
- **实事求是**：完全基于代码分析结果描述，不要臆测或推断未实现的功能
- **描述详细、具体**：避免空洞的描述，基于真实代码逻辑展开
- **整合多个技术模块**：统一从产品视角描述功能，而不是罗列技术实现
"""

    @staticmethod
    def _get_function_description_format() -> str:
        """获取功能描述格式要求"""
        return """## 功能描述格式

#### 2.X {{功能点名称}}
- **功能描述**：这个功能是什么，解决什么问题
- **使用场景**：用户在什么情况下会使用这个功能（举2-3个具体场景）
- **业务流程**：详细描述用户与系统的交互过程
  - 如果流程简单（3步以内），直接用文字描述
  - 如果流程复杂（多分支、多角色交互），可考虑使用 Mermaid sequenceDiagram
- **业务规则**：该功能需要遵循的业务规则和约束条件
- **异常处理**：可能出现的异常情况及系统的处理方式
- **数据流转**（可选）：如果数据流转路径复杂，可使用 Mermaid flowchart 或文字说明
"""

    @staticmethod
    def _get_diagram_usage_principles() -> str:
        """获取流程图使用原则"""
        return """## 流程图使用原则（可选，非强制）
- 只在流程复杂、用图表比文字更清晰时才使用 Mermaid
- 简单的流程用文字描述即可
- 如果使用流程图：
  - 交互流程使用 sequenceDiagram（展示用户-系统交互）
  - 数据流转使用 flowchart（展示数据流动）
- 判断标准：是否真的帮助理解？还是为了凑图而画图？
"""

    @staticmethod
    def _get_document_structure_requirements(include_subdomain_guide: bool = True) -> str:
        """
        获取文档结构要求

        Args:
            include_subdomain_guide: 是否包含子域组织指南
        """
        subdomain_guide = ""
        if include_subdomain_guide:
            subdomain_guide = """
**如果该功能域有二级子域**：
- 按子域组织功能描述（如：2.1 子域1的功能，2.2 子域2的功能）
- 每个子域下再详细描述具体功能点

**如果该功能域无子域**：
- 直接列出所有核心功能（2.1 功能1，2.2 功能2...）
"""

        return f"""## 文档结构要求

### 第1章：功能域概述
- **1.1 功能定位**：描述该功能域在整个产品中的位置和作用
- **1.2 业务价值**：为用户/业务带来的核心价值
- **1.3 核心能力列表**：列出该功能域提供的主要能力（3-8个）
- **1.4 子域结构**（如果有）：如果该功能域包含二级子域，说明子域的划分逻辑和各自职责

### 第2章：功能详细说明
对每个核心能力进行详细描述。
{subdomain_guide}
### 第3章：跨功能交互
- **3.1 对外交互**：该功能域与其他功能域的协作关系
- **3.2 数据依赖**：依赖哪些外部数据或服务

### 第4章：业务约束与限制
列出该功能域的业务约束、限制条件、性能特点等
"""

    @staticmethod
    def _get_output_format_requirement(full_document: bool = True) -> str:
        """
        获取输出格式要求

        Args:
            full_document: 是否输出完整文档（False表示只输出第2章）
        """
        if full_document:
            return """## 输出格式
- **必须使用中文**输出所有内容
- 直接输出 Markdown 格式的 PRD 文档，不要有任何前置说明
"""
        else:
            return """## 输出格式
- **必须使用中文**输出所有内容
- 直接输出第2章的功能详细说明部分（只输出功能描述，不要输出"## 第2章"标题），不要有任何前置说明
"""

    @staticmethod
    def _get_prd_quality_requirements() -> str:
        """
        获取PRD生成的完整质量要求（组合所有子部分）

        Returns:
            质量要求的提示词文本
        """
        return f"""
{PRDPromptBuilder._get_language_style_requirements()}

{PRDPromptBuilder._get_content_quality_requirements()}

{PRDPromptBuilder._get_function_description_format()}

{PRDPromptBuilder._get_diagram_usage_principles()}
"""

    @staticmethod
    def build_domain_prd_prompt_first_batch(
        domain_info: Dict[str, Any],
        batch_modules: List[Dict[str, Any]],
        total_modules: int,
        repo_path: str
    ) -> str:
        """
        构建第一批PRD生成提示词（包含完整框架）

        Args:
            domain_info: 功能域信息
            batch_modules: 本批次的模块数据
            total_modules: 总模块数量
            repo_path: 仓库路径

        Returns:
            提示词字符串
        """
        domain_name = domain_info.get('domain_name', '未命名功能域')
        domain_description = domain_info.get('domain_description', '')
        business_value = domain_info.get('business_value', '')
        sub_domains = domain_info.get('sub_domains', [])

        # 准备子域信息
        sub_domains_info = ""
        if sub_domains:
            sub_domains_info = "\n\n# 功能域层级结构\n该功能域包含以下二级子域：\n"
            for i, sub in enumerate(sub_domains, 1):
                sub_domains_info += f"{i}. **{sub.get('sub_domain_name', '')}**\n"
                sub_domains_info += f"   - 定位：{sub.get('sub_domain_description', '')}\n"
                sub_domains_info += f"   - 包含模块：{', '.join(sub.get('technical_modules', []))}\n"

        modules_json = json.dumps(batch_modules, ensure_ascii=False, indent=2)

        prompt = f"""你是一位资深的产品经理，需要为产品功能域编写详细的产品需求文档（PRD）。

# 项目信息
- **项目路径**: {repo_path}

# 分批生成说明
该功能域共包含 {total_modules} 个技术模块。由于内容较多，将分批生成。
**本次是第 1 批**，将处理前 {len(batch_modules)} 个模块。

# 要求
1. 生成完整的PRD框架（包括第1章概述、第3-4章）
2. 第2章"功能详细说明"中，详细描述本批次模块的所有功能
3. 如果还有后续批次，在第2章末尾注明"更多功能将在下一部分补充"

# 功能域信息
- **功能域名称**: {domain_name}
- **功能域定位**: {domain_description}
- **业务价值**: {business_value}
{sub_domains_info}
# 本批次技术模块
{modules_json}

# PRD 编写要求

{PRDPromptBuilder._get_document_structure_requirements(include_subdomain_guide=True)}

{PRDPromptBuilder._get_prd_quality_requirements()}

{PRDPromptBuilder._get_output_format_requirement(full_document=True)}
"""
        return prompt

    @staticmethod
    def build_domain_prd_prompt_continuation(
        domain_info: Dict[str, Any],
        batch_modules: List[Dict[str, Any]],
        batch_num: int,
        total_batches: int,
        repo_path: str
    ) -> str:
        """
        构建后续批次PRD生成提示词（只生成功能详细说明）

        Args:
            domain_info: 功能域信息
            batch_modules: 本批次的模块数据
            batch_num: 当前批次编号
            total_batches: 总批次数
            repo_path: 仓库路径

        Returns:
            提示词字符串
        """
        domain_name = domain_info.get('domain_name', '未命名功能域')
        domain_description = domain_info.get('domain_description', '')
        business_value = domain_info.get('business_value', '')
        sub_domains = domain_info.get('sub_domains', [])

        # 准备子域信息
        sub_domains_info = ""
        if sub_domains:
            sub_domains_info = "\n\n# 功能域层级结构（重要参考）\n该功能域包含以下二级子域，请按此结构组织内容：\n"
            for i, sub in enumerate(sub_domains, 1):
                sub_domains_info += f"{i}. **{sub.get('sub_domain_name', '')}**\n"
                sub_domains_info += f"   - 定位：{sub.get('sub_domain_description', '')}\n"
                sub_domains_info += f"   - 包含模块：{', '.join(sub.get('technical_modules', []))}\n"

        modules_json = json.dumps(batch_modules, ensure_ascii=False, indent=2)

        prompt = f"""你是一位资深的产品经理，正在继续编写产品功能域的PRD文档。

# 项目信息
- **项目路径**: {repo_path}

# 任务说明
功能域 **{domain_name}** 的PRD已经生成了框架和第一部分功能。
现在需要补充第 {batch_num}/{total_batches} 批模块的功能详细说明。

# 功能域上下文（保持一致性）
- **功能域名称**: {domain_name}
- **功能域定位**: {domain_description}
- **业务价值**: {business_value}
{sub_domains_info}
# 本批次技术模块
{modules_json}

# 要求
1. **只生成"第2章：功能详细说明"的内容**
2. 详细描述本批次模块的所有功能
3. 继续使用产品语言，风格与之前保持一致
4. 避免重复已经描述过的内容
5. **章节编号**：第2章的功能点编号请连续编号（不要从2.1重新开始）
6. **子域组织**（如果有子域）：按照功能域层级结构组织内容，确保本批次的模块归入正确的子域

{PRDPromptBuilder._get_prd_quality_requirements()}

## 风格一致性与衔接（重要）
- **保持风格一致**：与第一批使用相同的描述风格、深度和术语
- **自然衔接**：内容应该能无缝拼接到第一批之后，不要重复章节标题
- **连贯性**：虽然是分批生成，但最终应该像是一个整体

{PRDPromptBuilder._get_output_format_requirement(full_document=False)}
"""
        return prompt

