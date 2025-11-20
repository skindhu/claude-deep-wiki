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
from utils.semantic_prompt_builder import SemanticPromptBuilder
from utils.json_extractor import JSONExtractor
from utils.claude_query_helper import ClaudeQueryHelper

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
        modules = structure_data.get('modules', [])
        if not modules:
            raise ValueError("输入数据中没有模块信息")

        # 过滤排除的模块
        from config import EXCLUDE_MODULES
        if EXCLUDE_MODULES:
            original_count = len(modules)
            modules = [m for m in modules if m.get('name') not in EXCLUDE_MODULES]
            filtered_count = original_count - len(modules)
            if filtered_count > 0:
                print(f"  ⚠️  已过滤 {filtered_count} 个模块: {', '.join(sorted(EXCLUDE_MODULES))}")

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
        层次化分析单个模块

        分析顺序：
        1. 主模块的 all_files（如果有）
        2. 遍历每个 sub_module 的 all_files

        Args:
            module: 模块信息
            repo_path: 仓库路径

        Returns:
            {
                "main_module": {...},
                "sub_modules": {...},
                "status": "success"
            }
        """
        module_name = module.get('name', 'Unknown')

        # 检查完整缓存
        cache_key = f"detailed/{module_name}/complete"
        cached_complete = self.debug_helper.load_cached_data(cache_key)
        if cached_complete:
            print(f"    ✓ 加载完整缓存")
            return cached_complete

        results = {}

        # 1. 分析主模块层级的文件
        main_files = module.get('all_files', [])
        if main_files:
            print(f"    → 分析主模块文件: {len(main_files)} 个")

            # 检查主模块缓存
            main_cache_key = f"detailed/{module_name}/main_module"
            cached_main = self.debug_helper.load_cached_data(main_cache_key)

            if cached_main:
                print(f"       ✓ 加载主模块缓存")
                main_result = cached_main
            else:
                main_result = await self._analyze_files_batch(
                    module_name=module_name,
                    sub_name=None,
                    scope="main",
                    files=main_files,
                    description=module.get('responsibility', ''),
                    repo_path=repo_path
                )
                # 保存主模块结果
                self.debug_helper.save_stage_data(
                    main_cache_key,
                    self.last_response,
                    main_result
                )

            results['main_module'] = main_result

        # 2. 分析每个子模块
        sub_modules = module.get('sub_modules', [])
        results['sub_modules'] = {}

        for idx, sub_module in enumerate(sub_modules, 1):
            sub_name = sub_module.get('name', f'SubModule_{idx}')
            sub_files = sub_module.get('all_files', [])

            if sub_files:
                print(f"    → 分析子模块 [{idx}/{len(sub_modules)}]: {sub_name} ({len(sub_files)} 个文件)")

                # 检查子模块缓存
                sub_cache_key = f"detailed/{module_name}/sub_modules/{sub_name}"
                cached_sub = self.debug_helper.load_cached_data(sub_cache_key)

                if cached_sub:
                    print(f"       ✓ 加载子模块缓存")
                    sub_result = cached_sub
                else:
                    sub_result = await self._analyze_files_batch(
                        module_name=module_name,
                        sub_name=sub_name,
                        scope="sub_module",
                        files=sub_files,
                        description=sub_module.get('description', ''),
                        repo_path=repo_path
                    )
                    # 保存子模块结果
                    self.debug_helper.save_stage_data(
                        sub_cache_key,
                        self.last_response,
                        sub_result
                    )

                results['sub_modules'][sub_name] = sub_result

        # 保存完整结果
        results['status'] = 'success'
        self.debug_helper.save_stage_data(
            cache_key,
            None,
            results
        )

        return results

    async def _analyze_files_batch(
        self,
        module_name: str,
        sub_name: str,
        scope: str,
        files: List[str],
        description: str,
        repo_path: str
    ) -> Dict[str, Any]:
        """
        分批分析文件列表

        Args:
            module_name: 模块名称
            sub_name: 子模块名称（主模块时为None）
            scope: 分析范围（"main" 或 "sub_module"）
            files: 文件路径列表
            description: 模块/子模块描述
            repo_path: 仓库路径

        Returns:
            分析结果 {
                "files_analysis": [...],
                "file_count": N
            }
        """
        # 创建固定大小的批次（12个文件）
        batches = self._create_fixed_size_batches(files, batch_size=12)

        batch_results = []
        for idx, batch in enumerate(batches, 1):
            print(f"       批次 [{idx}/{len(batches)}]: {len(batch)} 个文件")

            # 检查批次缓存
            # 主模块：detailed/{module_name}/batched/{module_name}_main_batch_01
            # 子模块：detailed/{module_name}/batched/{full_name}_sub_module_batch_01
            full_name = f"{module_name}.{sub_name}" if sub_name else module_name
            cache_key = f"detailed/{module_name}/batched/{full_name}_{scope}_batch_{idx:02d}"
            cached = self.debug_helper.load_cached_data(cache_key)

            if cached:
                batch_results.append(cached)
                continue

            # 构建提示词
            prompt = SemanticPromptBuilder.build_batch_analysis_prompt(
                module_name=full_name,
                description=description,
                repo_path=repo_path,
                files=batch,
                batch_idx=idx,
                total_batches=len(batches)
            )

            # 调用Claude分析
            response, result = await ClaudeQueryHelper.query_with_json_retry(
                client=self.client,
                prompt=prompt,
                session_id=f"semantic_{full_name}",
                max_attempts=3,
                validator=lambda r: r and r.get('files_analysis')
            )

            self.last_response = response
            batch_results.append(result)
            self.debug_helper.save_stage_data(cache_key, response, result)

        # 合并所有批次结果
        return self._merge_batch_results(batch_results, files)

    def _create_fixed_size_batches(
        self,
        files: List[str],
        batch_size: int = 8
    ) -> List[List[str]]:
        """
        创建固定大小的文件批次

        Args:
            files: 文件列表
            batch_size: 每批文件数（默认8个，范围5-10）

        Returns:
            批次列表，每个批次包含最多batch_size个文件
        """
        batches = []
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batches.append(batch)
        return batches

    def _merge_batch_results(
        self,
        batch_results: List[Dict],
        files: List[str]
    ) -> Dict[str, Any]:
        """
        合并所有批次的分析结果

        Args:
            batch_results: 所有批次的结果列表
            files: 文件路径列表

        Returns:
            合并后的结果 {
                "files_analysis": [...],
                "file_count": N
            }
        """
        # 1. 合并所有文件分析
        all_files_analysis = []
        for batch_result in batch_results:
            all_files_analysis.extend(batch_result.get('files_analysis', []))

        # 2. 去重（如果有重复分析的文件）
        seen_files = set()
        deduplicated_analysis = []
        for file_analysis in all_files_analysis:
            file_path = file_analysis.get('file_path', '')
            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                deduplicated_analysis.append(file_analysis)

        # 3. 构建结果
        return {
            "files_analysis": deduplicated_analysis,
            "file_count": len(files)
        }

    async def disconnect(self):
        """断开连接并清理资源"""
        if self._connected:
            await self.client.disconnect()
            self._connected = False


# ============================================================================
# 独立测试接口
# ============================================================================

async def test_semantic_analyzer(repo_path: str = None):
    """
    独立测试语义分析 Agent

    Args:
        repo_path: 仓库路径，如果为None则从命令行参数读取
    """
    # 添加路径以导入其他模块
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.debug_helper import DebugHelper
    from agents.structure_scanner_agent import StructureScannerAgent

    # 测试参数：从参数或命令行获取
    if repo_path is None:
        if len(sys.argv) > 1:
            repo_path = sys.argv[1]
        else:
            print("❌ 错误: 请提供仓库路径作为参数")
            print("   用法: python semantic_analyzer_agent.py <repo_path>")
            return

    if not repo_path or not Path(repo_path).exists():
        print(f"❌ 错误: 仓库路径不存在: {repo_path}")
        return

    print("=" * 60)
    print("🧪 语义分析 Agent 独立测试")
    print("=" * 60)

    # 创建 Debug Helper
    debug_helper = DebugHelper(enabled=True)

    # 步骤1: 获取结构数据
    print("\n步骤1: 获取结构数据...")
    scanner = StructureScannerAgent(debug_helper)

    try:
        structure_data = await scanner.scan_repository(repo_path)
        print(f"✅ 获取到 {len(structure_data.get('modules', []))} 个模块")
    except Exception as e:
        print(f"❌ 结构扫描失败: {e}")
        return
    finally:
        await scanner.disconnect()

    # 步骤2: 执行语义分析
    print("\n步骤2: 执行语义分析...")
    analyzer = SemanticAnalyzerAgent(debug_helper)

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
                # 新格式：main_module 和 sub_modules
                main_module = module_result.get('main_module', {})
                sub_modules = module_result.get('sub_modules', {})

                main_file_count = main_module.get('file_count', 0)
                sub_module_count = len(sub_modules)

                print(f"   主模块文件数: {main_file_count}")
                print(f"   子模块数量: {sub_module_count}")

                # 统计总文件分析数
                total_analyzed = len(main_module.get('files_analysis', []))
                for sub_result in sub_modules.values():
                    total_analyzed += len(sub_result.get('files_analysis', []))

                print(f"   总分析文件数: {total_analyzed}")

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
    # 从命令行参数读取仓库路径
    asyncio.run(test_semantic_analyzer())

