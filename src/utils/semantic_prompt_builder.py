"""
Semantic Prompt Builder - 语义分析提示词构建器

负责构建所有与语义分析相关的提示词
"""

import json
from typing import Dict, Any, List


class SemanticPromptBuilder:
    """语义分析提示词构建器"""

    @staticmethod
    def build_overview_prompt(
        module_name: str,
        responsibility: str,
        layer: str,
        repo_path: str,
        key_files_info: List[Dict]
    ) -> str:
        """
        构建概览分析提示词

        Args:
            module_name: 模块名称
            responsibility: 模块职责
            layer: 模块层次
            repo_path: 仓库路径
            key_files_info: 关键文件信息列表

        Returns:
            提示词字符串
        """
        return f"""你是业务分析专家。请分析这个模块的业务价值和核心功能。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 阶段1 任务：模块概览分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**模块信息**:
- 模块名称: {module_name}
- 初步职责: {responsibility}
- 模块层次: {layer}
- 仓库路径: {repo_path}

**关键文件信息**:
{json.dumps(key_files_info, ensure_ascii=False, indent=2)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 分析任务
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **理解业务价值**: 这个模块为用户/系统提供什么价值？
2. **识别核心功能**: 提炼3-5个主要业务功能点
3. **分析交互关系**: 这个模块与哪些其他模块有交互？
4. **使用业务语言**: 描述时避免技术术语，面向产品经理和业务人员

⚠️ 重要约束:
- 基于文件路径、导入导出关系进行推断
- 不要读取文件内容（留给阶段2）
- 保持简洁，每个功能描述1-2句话

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 输出格式（必须是完整的 JSON）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```json
{{
  "module_name": "{module_name}",
  "business_purpose": "这个模块的业务价值是...",
  "core_features": [
    {{
      "feature_name": "功能名称",
      "description": "功能描述",
      "related_files": ["file1.js", "file2.js"]
    }}
  ],
  "external_interactions": [
    {{
      "target_module": "目标模块名",
      "interaction_type": "调用/被调用/数据传递",
      "description": "交互说明"
    }}
  ]
}}
```

**重要**: 输出必须是有效的 JSON，不要在 JSON 前后添加说明文字。
"""

    @staticmethod
    def build_batch_analysis_prompt(
        module_name: str,
        business_purpose: str,
        repo_path: str,
        files_to_analyze: List[Dict],
        batch_idx: int = None,
        total_batches: int = None,
        batch_cohesion: float = None,
        batch_description: str = None
    ) -> str:
        """
        构建批次分析提示词

        Args:
            module_name: 模块名称
            business_purpose: 业务价值
            repo_path: 仓库路径
            files_to_analyze: 需要分析的文件列表
            batch_idx: 当前批次索引（可选）
            total_batches: 总批次数（可选）
            batch_cohesion: 批次关联度（可选）
            batch_description: 批次描述（可选）

        Returns:
            提示词字符串
        """
        # 批次上下文说明
        batch_context = ""
        if total_batches and total_batches > 1:
            batch_context = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 批次信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**当前批次**: 第 {batch_idx}/{total_batches} 批
**批次关联度**: {batch_cohesion}
**批次描述**: {batch_description}

⚠️ 重要提示：
- 这是批量分析的一部分，请保持分析风格的一致性
- 与其他批次的文件可能存在关联，请在必要时说明
- 专注于当前批次的文件，不要臆测其他批次的内容
"""

        return f"""你是资深的业务逻辑分析专家。你的核心任务是**深入理解代码背后的业务逻辑实现**。
{batch_context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 阶段2 任务：深度业务逻辑分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🎯 核心目标**: 不是简单描述代码做了什么，而是深入解释**为什么这样做、业务上如何运作、对用户有什么影响**。

**模块信息**:
- 模块名称: {module_name}
- 业务价值: {business_purpose}
- 仓库路径: {repo_path}

**本批次需要分析的文件** ({len(files_to_analyze)} 个):
{json.dumps([f.get('path', '') for f in files_to_analyze], ensure_ascii=False, indent=2)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 深度分析任务（对每个文件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**对每个文件执行以下深度分析**:

1. **使用 analyze_code_block 工具**:
   - 读取文件内容
   - 调用 analyze_code_block 工具获取代码结构
   - 参数: code=文件内容, language=编程语言, context={{module: "{module_name}"}}

2. **深入分析业务逻辑实现**:
   - **业务目的**: 这个函数解决什么业务问题？为什么需要它？
   - **输入参数**: 每个参数的业务含义、取值范围、业务约束
   - **输出结果**: 返回值的业务含义、对业务流程的影响
   - **详细业务逻辑**:
     * 完整的业务处理步骤（7-10步，尽可能详细）
     * 每一步的业务含义和为什么这样做
     * 关键的业务决策点（if/switch）及决策依据
     * 循环处理的业务场景（为什么需要遍历）
     * 数据转换的业务意义（为什么这样转换）
   - **业务规则与约束**:
     * 业务验证规则（如：金额必须>0）
     * 业务流程约束（如：必须先登录才能下单）
     * 权限控制逻辑
   - **异常与边界情况**:
     * 各种异常的业务含义
     * 边界值的业务处理
     * 降级方案和补偿机制
   - **业务影响**:
     * 对用户体验的影响
     * 对数据状态的改变
     * 对其他业务流程的连锁影响

3. **使用业务语言描述实现细节**:
   - ❌ 错误: "该函数调用了 getUserById 方法"
   - ✅ 正确: "系统首先验证用户ID的合法性，然后从数据库获取用户详细信息，包括基本资料、权限级别和账户状态，最后根据用户的会员等级决定返回的数据范围"
   - ❌ 错误: "循环遍历订单列表"
   - ✅ 正确: "逐个检查用户的历史订单，筛选出30天内的有效订单，计算总消费金额以判断是否达到升级VIP的条件"

4. **业务逻辑深度分析示例**:

   示例函数: `processOrder(orderId, userId)`

   ❌ **浅层分析**（避免）:
   ```
   这个函数处理订单，接收订单ID和用户ID，返回处理结果。
   步骤：
   1. 获取订单
   2. 验证用户
   3. 处理订单
   4. 返回结果
   ```

   ✅ **深度业务逻辑分析**（目标）:
   ```
   业务目的: 处理用户提交的订单，完成从订单验证到支付确认的完整业务流程

   详细业务逻辑:
   1. [数据获取] 根据订单ID从数据库获取订单详情
      - 业务原因: 需要完整的订单信息才能进行后续处理
      - 决策点: 如果订单不存在，返回"订单未找到"错误
      - 业务规则: 只能处理状态为"待支付"的订单

   2. [权限验证] 验证用户是否有权限操作此订单
      - 业务原因: 防止用户操作他人的订单，保护交易安全
      - 决策点: 如果订单归属用户ID与当前用户ID不匹配，拒绝操作
      - 业务影响: 保护用户隐私和财产安全

   3. [库存检查] 检查订单中所有商品的库存
      - 业务原因: 确保有足够库存完成交易，避免超卖
      - 决策点: 如果任一商品库存不足，标记该商品并询问用户是否继续
      - 业务规则: 库存检查必须是原子操作，防止并发问题

   4. [价格计算] 重新计算订单总价
      - 业务原因: 防止价格篡改，使用最新的商品价格和优惠信息
      - 业务规则:
         * 应用用户的会员折扣
         * 应用优惠券（如果有）
         * 计算运费（根据配送地址）
      - 决策点: 如果计算的价格与订单价格差异>1%，提示用户价格变动

   5. [支付处理] 调用支付网关完成支付
      - 业务原因: 收取用户款项，完成交易闭环
      - 异常处理:
         * 余额不足: 提示用户充值或使用其他支付方式
         * 支付超时: 保留订单15分钟，允许重试
         * 网络异常: 进入待确认状态，通过回调确认支付结果

   6. [库存扣减] 扣减商品库存
      - 业务原因: 支付成功后需要预留商品，防止其他用户购买
      - 业务规则: 使用分布式锁确保库存扣减的准确性
      - 补偿机制: 如果后续步骤失败，需要回滚库存

   7. [订单状态更新] 将订单状态从"待支付"改为"已支付"
      - 业务原因: 标记订单已完成支付，触发后续的发货流程
      - 业务影响:
         * 仓库系统会接收到拣货任务
         * 用户会收到支付成功通知
         * 积分系统会增加用户积分

   8. [通知发送] 发送支付成功通知给用户
      - 业务原因: 告知用户支付结果，提升用户体验
      - 通知渠道: 站内信、邮件、短信（根据用户设置）
      - 异常处理: 通知失败不影响订单流程，会异步重试
   ```

⚠️ 重要约束:
- **必须**使用 analyze_code_block 工具分析每个文件
- **基于真实代码**，不得编造函数或功能
- **工具调用预算**: 最多调用 {len(files_to_analyze)} 次 analyze_code_block
- 如果文件过大或分析失败，跳过该文件并记录

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 输出格式（必须是完整的 JSON）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```json
{{
  "files_analysis": [
    {{
      "file_path": "相对路径",
      "language": "编程语言",
      "functions": [
        {{
          "name": "函数名",
          "business_purpose": "解决什么业务问题，为什么需要这个函数",
          "input_params": [
            {{
              "name": "参数名",
              "type": "类型",
              "business_meaning": "业务含义",
              "constraints": "取值范围和业务约束"
            }}
          ],
          "output": {{
            "type": "返回值类型",
            "business_meaning": "返回值的业务含义",
            "business_impact": "对业务流程的影响"
          }},
          "detailed_business_logic": [
            {{
              "step": 1,
              "action": "具体操作",
              "business_reason": "为什么这样做",
              "decision_point": "是否包含业务决策（如if判断）",
              "business_rule": "涉及的业务规则"
            }},
            {{
              "step": 2,
              "action": "...",
              "business_reason": "...",
              "decision_point": "...",
              "business_rule": "..."
            }}
          ],
          "business_rules": [
            "业务规则1：金额必须大于0",
            "业务规则2：必须先登录才能访问"
          ],
          "exception_handling": [
            {{
              "exception_type": "异常类型",
              "business_meaning": "这个异常在业务上意味着什么",
              "handling_strategy": "如何处理",
              "business_impact": "对用户的影响"
            }}
          ],
          "edge_cases": [
            {{
              "scenario": "边界场景描述",
              "handling": "如何处理",
              "business_reason": "为什么这样处理"
            }}
          ]
        }}
      ],
      "classes": [
        {{
          "name": "类名",
          "business_purpose": "这个类在业务中的角色和职责",
          "business_scenario": "主要应用场景",
          "state_management": "管理哪些业务状态",
          "key_methods": [
            {{
              "name": "方法名",
              "business_purpose": "业务用途",
              "when_to_call": "什么业务场景下调用",
              "business_impact": "对业务的影响"
            }}
          ],
          "business_relationships": [
            {{
              "related_class": "关联的类",
              "relationship_type": "has-a/uses/extends",
              "business_meaning": "这种关联在业务上的意义"
            }}
          ]
        }}
      ],
      "business_flow": {{
        "description": "这个文件中代码的整体业务流程",
        "entry_points": ["哪些函数是业务流程的入口"],
        "key_decision_points": ["关键的业务决策点"],
        "data_flow": "数据在业务流程中如何流转"
      }},
      "flow_diagram_mermaid": "sequenceDiagram\\n  ..."
    }}
  ]
}}
```

**重要**:
- 输出必须是有效的 JSON
- 不要在 JSON 前后添加说明文字
- 如果某个文件分析失败，在 files_analysis 中标记 error 字段
"""

