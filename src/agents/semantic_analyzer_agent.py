"""
Semantic Analyzer Agent - 语义分析 Agent

专注于代码的深度语义理解和业务逻辑分析。

职责:
1. 理解模块的业务价值和核心功能
2. 深入分析函数/类的业务逻辑
3. 提取业务流程和交互关系
4. 使用验证工具确保分析准确性
5. 生成面向业务的功能描述
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.code_analysis_server import create_code_analysis_mcp_server
from config import ANTHROPIC_AUTH_TOKEN, MAX_TURNS
from utils.batch_analyzer import FileAnalysisBatchManager
from utils.semantic_prompt_builder import SemanticPromptBuilder
from utils.json_extractor import JSONExtractor

logger = None  # 简化日志


class SemanticAnalyzerAgent:
    """语义分析 Agent - 专注于业务逻辑理解"""

    def __init__(self, debug_helper):
        """
        初始化语义分析 Agent

        Args:
            debug_helper: DebugHelper 实例
        """
        self.debug_helper = debug_helper
        self.last_response = ""  # 记录最后一次响应，用于调试保存
        self.batch_manager = None  # 延迟初始化批处理管理器

        # 创建 MCP Server
        self._mcp_server = create_code_analysis_mcp_server()

        # 创建 Claude Client
        self.client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                env={"ANTHROPIC_AUTH_TOKEN": ANTHROPIC_AUTH_TOKEN},
                mcp_servers={"code-analysis": self._mcp_server},
                allowed_tools=["code-analysis/*"],
                system_prompt="你是资深的代码架构师，擅长从技术代码中提炼业务逻辑和产品功能。",
                max_turns=MAX_TURNS,
                permission_mode="bypassPermissions"
            )
        )

        self._connected = False  # 连接状态

    async def analyze_semantics(
        self, structure_data: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        """
        完整语义分析（按模块进行三阶段分析）

        Args:
            structure_data: StructureScannerAgent 的输出结果
            repo_path: 仓库根目录路径

        Returns:
            {
                "modules_analysis": {
                    "模块名": {
                        "overview": {...},
                        "detailed_analysis": {...},
                        "validated_result": {...}
                    }
                },
                "analysis_metadata": {...}
            }
        """
        # 确保已连接
        if not self._connected:
            await self.client.connect()
            self._connected = True

        # 尝试加载完整缓存
        cached_final = self.debug_helper.load_cached_data("02_semantic_analysis_final")
        if cached_final:
            return cached_final

        # 提取模块列表
        modules = structure_data.get('module_hierarchy', {}).get('modules', [])
        if not modules:
            raise ValueError("输入数据中没有模块信息")

        # 按模块进行分析
        modules_analysis = {}

        for idx, module in enumerate(modules, 1):
            module_name = module.get('name', f'Module_{idx}')
            print(f"  [{idx}/{len(modules)}] 分析模块: {module_name}")

            try:
                module_result = await self._analyze_single_module(
                    module, repo_path
                )
                modules_analysis[module_name] = module_result

            except Exception as e:
                print(f"    ❌ 分析失败: {e}")
                modules_analysis[module_name] = {
                    "error": str(e),
                    "status": "failed"
                }

        # 构建最终结果
        final_result = {
            "modules_analysis": modules_analysis,
            "analysis_metadata": {
                "total_modules": len(modules),
                "analyzed_modules": len([m for m in modules_analysis.values() if m.get("status") != "failed"]),
                "failed_modules": len([m for m in modules_analysis.values() if m.get("status") == "failed"])
            }
        }

        # 保存最终结果
        self.debug_helper.save_stage_data(
            "02_semantic_analysis_final",
            self.last_response,
            final_result
        )

        return final_result

    async def _analyze_single_module(
        self, module: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        """
        分析单个模块（三阶段）

        Args:
            module: 模块信息
            repo_path: 仓库路径

        Returns:
            {
                "overview": {...},
                "detailed_analysis": {...},
                "validated_result": {...}
            }
        """
        module_name = module.get('name', 'Unknown')

        # 阶段1: 概览分析
        print(f"    → 概览分析...")
        cached_overview = self.debug_helper.load_cached_data(f"02_semantic_overview_{module_name}")
        if cached_overview:
            overview = cached_overview
        else:
            overview = await self._overview_analysis(module, repo_path)
            self.debug_helper.save_stage_data(
                f"02_semantic_overview_{module_name}",
                self.last_response,
                overview
            )

        # 阶段2: 细节挖掘（批量处理）
        print(f"    → 细节分析...")
        cached_details = self.debug_helper.load_cached_data(f"02_semantic_details_{module_name}")
        if cached_details:
            detailed_analysis = cached_details
        else:
            detailed_analysis = await self._detailed_analysis(module, overview, repo_path)
            self.debug_helper.save_stage_data(
                f"02_semantic_details_{module_name}",
                self.last_response,
                detailed_analysis
            )

        return {
            "overview": overview,
            "detailed_analysis": detailed_analysis,
            "status": "success"
        }

    async def _overview_analysis(
        self, module: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        """
        阶段1: 概览分析

        理解模块的整体职责、核心功能、业务价值

        Returns:
            {
                "module_name": "...",
                "business_purpose": "...",
                "core_features": [...],
                "external_interactions": [...]
            }
        """
        module_name = module.get('name', 'Unknown')
        responsibility = module.get('responsibility', '')
        layer = module.get('layer', '')
        key_files = module.get('key_files', [])

        # 准备关键文件信息
        key_files_info = []
        for kf in key_files[:10]:  # 最多10个关键文件
            key_files_info.append({
                "path": kf.get('path', ''),
                "imports": kf.get('imports', [])[:5],  # 简化，只列前5个
                "exports": kf.get('exports', [])[:5]
            })

        # 使用 PromptBuilder 构建提示词
        prompt = SemanticPromptBuilder.build_overview_prompt(
            module_name=module_name,
            responsibility=responsibility,
            layer=layer,
            repo_path=repo_path,
            key_files_info=key_files_info
        )

        # 每个模块使用独立session，但同一模块的overview和details共享session
        # 这样后续的详细分析可以基于overview建立的理解
        session_id = f"semantic_module_{module_name}"
        await self.client.query(prompt, session_id=session_id)

        # 接收响应
        response_text = ""
        async for message in self.client.receive_response():
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        response_text += block.text

        self.last_response = response_text

        # 提取 JSON
        overview = JSONExtractor.extract(response_text)

        if not overview or not overview.get('module_name'):
            raise ValueError("阶段1失败: 未返回有效的概览分析数据")

        return overview

    async def _detailed_analysis(
        self, module: Dict[str, Any], overview: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        """
        阶段2: 细节挖掘（批量处理版本）

        深入分析模块的所有文件

        Returns:
            {
                "files_analysis": [...],
                "batch_info": {...}
            }
        """
        module_name = module.get('name', 'Unknown')

        # 获取所有文件和关键文件
        all_files = module.get('all_files', [])
        key_files = module.get('key_files', [])

        # 初始化批处理管理器
        if not self.batch_manager:
            self.batch_manager = FileAnalysisBatchManager(repo_path)

        # 创建或查找批次专用目录
        batch_dir = self.debug_helper.create_batch_directory(module_name)

        # 尝试加载已有的批次信息
        batches = self.debug_helper.load_batches_info(batch_dir, module_name)
        files_to_analyze = None

        if not batches:
            # 需要重新计算批次
            files_to_analyze = self.batch_manager.prepare_files_with_dependencies(
                all_files, key_files
            )
            batches = self.batch_manager.create_file_batches(files_to_analyze)
            self.debug_helper.save_batches_info(batch_dir, module_name, batches, files_to_analyze)

        # 批次循环处理
        batch_results = []

        for idx, batch in enumerate(batches, 1):
            print(f"       批次 {idx}/{len(batches)}: {len(batch['files'])} 个文件")

            # 尝试加载已保存的批次结果
            cached_batch_result = self.debug_helper.load_batch_result(batch_dir, module_name, idx)

            if cached_batch_result and cached_batch_result.get('files_analysis'):
                batch_result = cached_batch_result
            else:
                # 需要重新分析
                prompt = self._build_batch_prompt(
                    module, overview, batch, repo_path, idx, len(batches)
                )

                # 使用与overview相同的session_id，让AI利用已建立的模块理解
                session_id = f"semantic_module_{module_name}"
                await self.client.query(prompt, session_id=session_id)

                # 接收响应
                response_text = ""
                async for message in self.client.receive_response():
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                response_text += block.text

                self.last_response = response_text

                # 提取JSON
                batch_result = JSONExtractor.extract(response_text)

                # 保存批次原始响应和提取结果
                self.debug_helper.save_batch_result(batch_dir, module_name, idx, response_text, batch_result, batch)

            # 保存批次结果到列表
            if batch_result and batch_result.get('files_analysis'):
                batch_results.append({
                    'batch_id': idx,
                    'files_analysis': batch_result['files_analysis'],
                    'batch_info': batch
                })

        # 智能合并所有批次结果
        if files_to_analyze is None:
            files_to_analyze = []
            for batch in batches:
                files_to_analyze.extend(batch.get('files', []))

        merged_result = self._merge_batch_results(
            batch_results, module, overview, files_to_analyze, batches
        )

        return merged_result

    def _build_batch_prompt(
        self,
        module: Dict[str, Any],
        overview: Dict[str, Any],
        batch: Dict[str, Any],
        repo_path: str,
        batch_idx: int,
        total_batches: int
    ) -> str:
        """
        构建批次分析提示词

        Args:
            module: 模块信息
            overview: 概览分析结果
            batch: 批次信息
            repo_path: 仓库路径
            batch_idx: 当前批次索引
            total_batches: 总批次数

        Returns:
            提示词字符串
        """
        module_name = module.get('name', 'Unknown')
        business_purpose = overview.get('business_purpose', '')
        files_to_analyze = batch['files']

        # 使用 PromptBuilder 构建提示词
        return SemanticPromptBuilder.build_batch_analysis_prompt(
            module_name=module_name,
            business_purpose=business_purpose,
            repo_path=repo_path,
            files_to_analyze=files_to_analyze,
            batch_idx=batch_idx,
            total_batches=total_batches,
            batch_cohesion=batch.get('cohesion'),
            batch_description=batch.get('description')
        )

    def _merge_batch_results(
        self,
        batch_results: List[Dict],
        module: Dict[str, Any],
        overview: Dict[str, Any],
        all_files: List[Dict],
        batches: List[Dict]
    ) -> Dict[str, Any]:
        """
        智能合并所有批次的分析结果

        Args:
            batch_results: 所有批次的结果列表
            module: 模块信息
            overview: 概览分析
            all_files: 所有文件信息
            batches: 批次信息列表

        Returns:
            合并后的完整结果
        """
        # 1. 简单合并所有文件分析
        all_files_analysis = []
        for batch_result in batch_results:
            all_files_analysis.extend(batch_result['files_analysis'])

        # 2. 去重（如果有重复分析的文件）
        seen_files = set()
        deduplicated_analysis = []
        for file_analysis in all_files_analysis:
            file_path = file_analysis.get('file_path', '')
            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                deduplicated_analysis.append(file_analysis)

        # 3. 统计信息
        total_files = len(all_files)
        analyzed_files = len(deduplicated_analysis)
        skipped_files = total_files - analyzed_files

        # 4. 提取关键业务实体（跨文件分析）
        all_functions = []
        all_classes = []

        for file_analysis in deduplicated_analysis:
            all_functions.extend(file_analysis.get('functions', []))
            all_classes.extend(file_analysis.get('classes', []))

        # 5. 构建跨文件关系图
        cross_file_relationships = self._build_cross_file_relationships(
            deduplicated_analysis
        )

        # 6. 构建最终结果
        merged_result = {
            "files_analysis": deduplicated_analysis,
            "batch_info": {
                "total_batches": len(batches),
                "total_files": total_files,
                "analyzed_files": analyzed_files,
                "skipped_files": skipped_files,
                "batch_details": [
                    {
                        "batch_id": b['batch_id'],
                        "file_count": len(b['files_analysis']),
                        "cohesion": b['batch_info']['cohesion']
                    }
                    for b in batch_results
                ]
            },
            "summary": {
                "total_functions": len(all_functions),
                "total_classes": len(all_classes),
                "has_cross_file_relationships": len(cross_file_relationships) > 0
            },
            "cross_file_relationships": cross_file_relationships
        }

        return merged_result

    def _build_cross_file_relationships(
        self, files_analysis: List[Dict]
    ) -> List[Dict]:
        """
        构建跨文件的业务关系

        识别文件间的引用、继承、组合等关系

        Args:
            files_analysis: 文件分析结果列表

        Returns:
            跨文件关系列表
        """
        relationships = []

        # 构建文件到类/函数的映射
        file_entities = {}
        for file_analysis in files_analysis:
            file_path = file_analysis.get('file_path', '')
            entities = []

            # 收集类
            for cls in file_analysis.get('classes', []):
                entities.append({
                    'type': 'class',
                    'name': cls.get('name', ''),
                    'file': file_path
                })

            # 收集函数
            for func in file_analysis.get('functions', []):
                entities.append({
                    'type': 'function',
                    'name': func.get('name', ''),
                    'file': file_path
                })

            file_entities[file_path] = entities

        # 简单的关系识别（基于类的 business_relationships）
        for file_analysis in files_analysis:
            for cls in file_analysis.get('classes', []):
                for rel in cls.get('business_relationships', []):
                    relationships.append({
                        'from_file': file_analysis.get('file_path', ''),
                        'from_entity': cls.get('name', ''),
                        'to_entity': rel.get('related_class', ''),
                        'relationship_type': rel.get('relationship_type', ''),
                        'business_meaning': rel.get('business_meaning', '')
                    })

        return relationships

    async def disconnect(self):
        """断开连接并清理资源"""
        if self._connected:
            await self.client.disconnect()
            self._connected = False


# ============================================================================
# 独立测试接口
# ============================================================================

async def test_semantic_analyzer():
    """独立测试语义分析 Agent"""
    import asyncio

    # 添加路径以导入其他模块
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.debug_helper import DebugHelper
    from agents.structure_scanner_agent import StructureScannerAgent

    # 测试参数
    repo_path = "/Users/huli/svn_work/xiaoyue_sdk_hippy"  # 修改为你的测试仓库路径

    print("=" * 60)
    print("🧪 语义分析 Agent 独立测试")
    print("=" * 60)

    # 创建 Debug Helper
    debug_helper = DebugHelper(enabled=True, verbose=True)

    # 步骤1: 获取结构数据
    print("\n步骤1: 获取结构数据...")
    scanner = StructureScannerAgent(debug_helper, verbose=True)

    try:
        structure_data = await scanner.scan_repository(repo_path)
        print(f"✅ 获取到 {len(structure_data.get('module_hierarchy', {}).get('modules', []))} 个模块")
    except Exception as e:
        print(f"❌ 结构扫描失败: {e}")
        return
    finally:
        await scanner.disconnect()

    # 步骤2: 执行语义分析
    print("\n步骤2: 执行语义分析...")
    analyzer = SemanticAnalyzerAgent(debug_helper, verbose=True)

    try:
        semantic_result = await analyzer.analyze_semantics(structure_data, repo_path)

        # 输出结果摘要
        print("\n" + "=" * 60)
        print("📊 语义分析结果摘要")
        print("=" * 60)

        metadata = semantic_result.get('analysis_metadata', {})
        print(f"\n总模块数: {metadata.get('total_modules', 0)}")
        print(f"分析成功: {metadata.get('analyzed_modules', 0)}")
        print(f"分析失败: {metadata.get('failed_modules', 0)}")

        modules_analysis = semantic_result.get('modules_analysis', {})
        for i, (module_name, module_result) in enumerate(list(modules_analysis.items())[:3], 1):
            print(f"\n{i}. {module_name}")
            if module_result.get('status') == 'failed':
                print(f"   状态: ❌ 失败")
                print(f"   错误: {module_result.get('error', 'Unknown')}")
            else:
                overview = module_result.get('overview', {})
                print(f"   业务价值: {overview.get('business_purpose', 'N/A')[:60]}...")
                features = overview.get('core_features', [])
                print(f"   核心功能数: {len(features)}")

                validated = module_result.get('validated_result', {})
                report = validated.get('validation_report', {})
                print(f"   置信度: {report.get('overall_confidence', 0.0):.2f}")

        if len(modules_analysis) > 3:
            print(f"\n   ... 还有 {len(modules_analysis) - 3} 个模块")

        print("\n✅ 测试完成！详细结果已保存到 output/debug/ 目录")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await analyzer.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_semantic_analyzer())

