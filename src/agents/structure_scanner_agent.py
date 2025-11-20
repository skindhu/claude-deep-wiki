"""
Structure Scanner Agent - 结构扫描 Agent

专注于代码仓库结构梳理，不做深度语义理解。

职责:
1. 扫描仓库完整结构
2. 识别模块层次（一级/二级/三级）
3. 分析模块依赖关系（基于导入导出）
4. 智能判断模块分层（core/business/utils）
5. 生成文件到模块的映射
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.code_analysis_server import create_code_analysis_mcp_server, scan_repository_structure
from config import ANTHROPIC_AUTH_TOKEN, MAX_TURNS, MODULE_FILE
from utils.structure_prompt_builder import StructurePromptBuilder
from utils.json_extractor import JSONExtractor
from utils.claude_query_helper import ClaudeQueryHelper
from utils.validator import StructureValidator

logger = None  # 简化日志


class StructureScannerAgent:
    """结构扫描 Agent - 专注于模块结构梳理"""

    def __init__(self, debug_helper):
        """
        初始化结构扫描 Agent

        Args:
            debug_helper: DebugHelper 实例
        """
        self.debug_helper = debug_helper
        self.last_response = ""  # 记录最后一次响应，用于调试保存

        # 创建 MCP Server
        self._mcp_server = create_code_analysis_mcp_server()

        # 创建验证器（延迟初始化，因为需要 client）
        self.validator = None

        # 创建 Claude Client
        self.client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                env={"ANTHROPIC_AUTH_TOKEN": ANTHROPIC_AUTH_TOKEN},
                mcp_servers={"code-analysis": self._mcp_server},
                allowed_tools=["code-analysis/*"],
                system_prompt="你是代码仓库结构分析专家，擅长识别项目模块划分和依赖关系。",
                max_turns=MAX_TURNS,
                model='claude-sonnet-4-5',
                permission_mode="bypassPermissions"  # 启用完全文件系统访问权限
            )
        )

        self._connected = False  # 连接状态

    async def scan_repository(self, repo_path: str) -> Dict[str, Any]:
        """
        完整扫描仓库结构（4阶段设计）

        阶段1: 结构扫描与模块识别
        阶段2: 文件覆盖率验证 + 修复
        阶段3: 大模块智能细分
        阶段4: 再次文件覆盖率验证 + 修复

        Args:
            repo_path: 仓库根目录路径

        Returns:
            {
                "project_info": {...},
                "modules": [...]
            }
        """
        # 确保已连接（首次调用时）
        if not self._connected:
            await self.client.connect()
            self._connected = True

            # 初始化验证器
            if self.validator is None:
                self.validator = StructureValidator(
                    client=self.client,
                    prompt_builder=StructurePromptBuilder
                )

        # 尝试加载完整缓存
        cached_final = self.debug_helper.load_cached_data("01_structure_scan_final")
        if cached_final:
            return cached_final

        # === 阶段 1/4: 结构扫描与模块识别 ===
        print("  → 阶段 1/4: 扫描项目结构与模块识别...")
        cached_overview = self.debug_helper.load_cached_data("01_structure_overview")
        if cached_overview:
            structure_overview = cached_overview
        else:
            structure_overview = await self._scan_and_identify_modules(repo_path)
            # 根据 all_files_patterns 填充 all_files
            print("     填充文件列表...")
            structure_overview = self._populate_all_files_from_patterns(structure_overview, repo_path)
            self.debug_helper.save_stage_data(
                "01_structure_overview",
                self.last_response,
                structure_overview
            )

        modules_count = len(structure_overview.get('modules', []))
        print(f"     识别到 {modules_count} 个模块")

        # === 阶段 2/4: 文件覆盖率验证 + 修复 ===
        print("\n  → 阶段 2/4: 文件覆盖率验证...")
        validation = self.validator.validate_file_coverage(
            structure_overview, repo_path
        )

        coverage_rate = validation['coverage_rate']
        print(f"     覆盖率: {coverage_rate:.1%} ({validation['total_in_modules']}/{validation['total_scanned']} 文件)")

        # 如果覆盖率低于 95%，使用 Claude 智能修复
        if coverage_rate < 0.95 and validation['orphan_files']:
            print(f"     ⚠️  发现 {len(validation['orphan_files'])} 个孤立文件")

            # 统计孤立文件类型
            orphan_by_lang = {}
            for f in validation['orphan_files']:
                lang = f.get('language', 'unknown')
                orphan_by_lang[lang] = orphan_by_lang.get(lang, 0) + 1

            print(f"     文件类型分布: {dict(sorted(orphan_by_lang.items(), key=lambda x: -x[1])[:5])}")
            print("     → 使用 Claude 智能修复...")

            structure_overview = await self.validator.fix_orphan_files_with_claude(
                structure_overview,
                validation['orphan_files'],
                repo_path
            )

            # 保存修复后的结构
            self.debug_helper.save_stage_data(
                "01_structure_overview_fixed",
                self.last_response,
                structure_overview
            )

            print("     ✓ 修复完成")
        else:
            print("     ✓ 覆盖率: 100%")

        # === 阶段 3/4: 大模块智能细分 ===
        print("\n  → 阶段 3/4: 大模块智能细分（依赖驱动）...")
        large_modules = self.validator.detect_large_modules(structure_overview)

        if large_modules:
            print(f"        检测到 {len(large_modules)} 个大模块")

            for idx, large_module in enumerate(large_modules, 1):
                await self._subdivide_large_module(
                    large_module, idx, len(large_modules), repo_path
                )
        else:
            print("        ✓ 无需细分")


        # 保存最终结果
        self.debug_helper.save_stage_data(
            "01_structure_scan_final",
            None,
            structure_overview
        )

        return structure_overview

    async def _subdivide_large_module(
        self,
        large_module: Dict[str, Any],
        idx: int,
        total_count: int,
        repo_path: str
    ) -> None:
        """
        细分单个大模块为子模块（包含缓存机制）

        Args:
            large_module: 大模块信息
            idx: 当前模块序号（从1开始）
            total_count: 大模块总数
            repo_path: 仓库路径
        """
        module_name = large_module['module_name']
        file_count = large_module['file_count']
        print(f"\n        ━━━ 细分模块 [{idx}/{total_count}]: {module_name} ({file_count} 个文件) ━━━")

        # 清理模块名称用于文件名（移除特殊字符）
        safe_module_name = module_name.replace('/', '_').replace(' ', '_')

        # 3.1: Claude 规划子模块
        cache_key_plan = f"planning/{safe_module_name}_01_subdivision_plan"
        cached_plan = self.debug_helper.load_cached_data(cache_key_plan)

        if cached_plan:
            print(f"        → 3.1: [缓存] 加载规划结果")
            subdivision_plan = cached_plan
        else:
            subdivision_plan = await self.validator.plan_module_subdivision(
                large_module
            )
            self.debug_helper.save_stage_data(
                cache_key_plan,
                self.validator.last_response,  # Claude 原始响应
                subdivision_plan
            )

        # 3.2: 依赖分析自动归属文件 + 循环依赖处理 ⭐
        cache_key_assign = f"planning/{safe_module_name}_02_auto_assigned"
        cached_assigned = self.debug_helper.load_cached_data(cache_key_assign)

        if cached_assigned:
            print(f"        → 3.2: [缓存] 加载自动归属结果")
            sub_modules_with_files = cached_assigned
        else:
            sub_modules_with_files = await self.validator.assign_files_by_dependency(
                large_module, subdivision_plan, repo_path
            )
            self.debug_helper.save_stage_data(
                cache_key_assign,
                None,
                sub_modules_with_files
            )

        # 3.3: Claude 验证修正
        verified_sub_modules = await self.validator.verify_subdivision_with_claude(
            large_module,
            sub_modules_with_files
        )

        # 3.4: 更新结构（原地修改）
        large_module['module_ref']['sub_modules'] = verified_sub_modules
        print(f"        ✓ 完成，生成 {len(verified_sub_modules)} 个子模块")

    def _populate_all_files_from_patterns(
        self, structure_overview: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        """
        根据 all_files_patterns 动态填充 all_files 字段

        Args:
            structure_overview: 结构概览（包含 all_files_patterns）
            repo_path: 仓库路径

        Returns:
            填充了 all_files 的结构概览
        """
        from pathlib import Path

        # 为每个模块填充 all_files
        modules_to_keep = []
        for module in structure_overview.get('modules', []):
            patterns = module.get('all_files_patterns', [])

            # 如果有 all_files_patterns，根据它填充 all_files
            if patterns:
                # 使用新的 MCP 工具进行文件过滤
                from mcp_servers.code_analysis_server import filter_files_by_patterns
                filter_result = filter_files_by_patterns(repo_path, patterns)

                if filter_result.get('success'):
                    matched_files = filter_result.get('matched_files', [])
                    module['all_files'] = matched_files

                    # 只保留匹配到文件的模块
                    if matched_files:
                        modules_to_keep.append(module)
                        print(f"     ✓ {module.get('name')}: {len(patterns)} 个规则 -> {len(matched_files)} 个文件")
                    else:
                        print(f"     ⚠️ {module.get('name')}: {len(patterns)} 个规则 -> 0 个文件（已过滤）")
                else:
                    print(f"     ⚠️ {module.get('name')}: 过滤失败 - {filter_result.get('error')}")
            else:
                # 没有 patterns 的模块也保留（可能是旧数据）
                modules_to_keep.append(module)

        # 更新模块列表，过滤掉空模块
        structure_overview['modules'] = modules_to_keep

        # 更新 project_info 中的 total_files 为实际分配到模块的文件数
        if 'project_info' in structure_overview:
            total_assigned_files = sum(len(m.get('all_files', [])) for m in modules_to_keep)
            structure_overview['project_info']['total_files'] = total_assigned_files

        return structure_overview

    async def _scan_and_identify_modules(self, repo_path: str) -> Dict[str, Any]:
        """
        阶段1: 结构扫描与模块识别

        工具调用: 1次 scan_repository_structure

        职责:
        - 扫描仓库结构
        - 识别所有业务功能模块
        - 选择关键文件（只有路径，不分析）
        - 初步判断模块分层
        - 列出所有相关文件

        Returns:
            {
                "project_info": {...},
                "modules": [
                    {
                        "name": "模块名",
                        "layer_guess": "business",
                        "responsibility": "简短描述",
                        "key_files_paths": ["path1", "path2"],
                        "all_files": [...]
                    }
                ]
            }
        """
        # 读取预定义模块（如果配置了MODULE_FILE）
        predefined_modules_content = None
        if MODULE_FILE:
            module_file_path = Path(MODULE_FILE)
            if module_file_path.exists():
                print(f"📋 正在加载预定义模块配置: {MODULE_FILE}")
                try:
                    with open(module_file_path, 'r', encoding='utf-8') as f:
                        predefined_modules_content = f.read().strip()
                    if predefined_modules_content:
                        print(f"✅ 成功加载模块配置 (长度: {len(predefined_modules_content)} 字符)")
                    else:
                        print(f"⚠️ 模块配置文件为空，将使用自动识别模式")
                        predefined_modules_content = None
                except Exception as e:
                    print(f"⚠️ 加载模块配置文件失败: {e}")
                    print("将使用自动识别模式")
            else:
                print(f"⚠️ 模块配置文件不存在: {MODULE_FILE}")
                print("将使用自动识别模式")

        # 使用 PromptBuilder 构建提示词，让 Claude 通过工具调用获取扫描结果
        prompt = StructurePromptBuilder.build_scan_and_identify_prompt(
            repo_path, predefined_modules_content
        )

        # Phase 1 使用独立session
        # 原因：下一阶段会通过结构化数据传递输出，不需要对话历史

        # 使用带重试的查询，验证返回的JSON包含modules字段
        response_text, overview = await ClaudeQueryHelper.query_with_json_retry(
            client=self.client,
            prompt=prompt,
            session_id="structure_scan_phase1",
            max_attempts=3,
            validator=lambda r: r and r.get('modules')
        )

        self.last_response = response_text
        return overview

    async def _analyze_file_dependencies(
        self, structure_overview: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        """
        阶段2: 依赖分析

        工具调用: 50次 extract_imports_and_exports

        职责:
        - 从阶段1结果中提取所有关键文件路径
        - 逐个分析关键文件
        - 提取 imports/exports
        - 不做复杂推理

        Returns:
            {
                "file_dependencies": [
                    {
                        "path": "src/module/main.js",
                        "imports": [...],
                        "exports": [...],
                        "language": "javascript",
                        "module": "模块名"
                    }
                ]
            }
        """
        modules = structure_overview.get('modules', [])

        # 收集所有关键文件
        all_key_files = []
        for module in modules:
            key_paths = module.get('key_files_paths', [])
            for path in key_paths:
                all_key_files.append({
                    'path': path,
                    'module': module.get('name', 'Unknown')
                })

        # 使用 PromptBuilder 构建提示词
        prompt = StructurePromptBuilder.build_file_dependencies_prompt(
            repo_path, all_key_files
        )

        # Phase 2 使用独立session，避免Phase 1对话历史的冗余
        # 必要的信息已通过 all_key_files 参数显式传递

        # 使用带重试的查询，验证返回的JSON包含file_dependencies字段
        response_text, dependencies = await ClaudeQueryHelper.query_with_json_retry(
            client=self.client,
            prompt=prompt,
            session_id="structure_scan_phase2",
            max_attempts=3,
            validator=lambda r: r and r.get('file_dependencies')
        )

        self.last_response = response_text
        return dependencies

    async def _finalize_structure(
        self, structure_overview: Dict[str, Any], dependencies: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        阶段3: 综合分析

        工具调用: 0次（纯分析）

        职责:
        - 将依赖信息整合回模块
        - 基于真实依赖精确分层
        - 构建依赖图
        - 生成文件映射

        Returns:
            {
                "project_info": {...},
                "module_hierarchy": {...},
                "dependency_graph": {...},
                "file_module_mapping": {...}
            }
        """
        # 使用 PromptBuilder 构建提示词
        prompt = StructurePromptBuilder.build_finalize_structure_prompt(
            structure_overview, dependencies
        )

        # Phase 3 使用独立session，避免前两阶段对话历史的冗余
        # Phase 1和2的输出已通过 structure_overview 和 dependencies 参数显式传递

        # 使用带重试的查询，验证返回的JSON包含module_hierarchy字段
        response_text, final_structure = await ClaudeQueryHelper.query_with_json_retry(
            client=self.client,
            prompt=prompt,
            session_id="structure_scan_phase3",
            max_attempts=3,
            validator=lambda r: r and r.get('module_hierarchy')
        )

        self.last_response = response_text
        return final_structure

    async def disconnect(self):
        """断开连接并清理资源"""
        if self._connected:
            await self.client.disconnect()
            self._connected = False


# ============================================================================
# 独立测试接口
# ============================================================================

async def test_scanner(repo_path: str = None):
    """
    独立测试结构扫描 Agent

    Args:
        repo_path: 仓库路径，如果为None则从命令行参数读取
    """
    # 添加路径以导入其他模块
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.debug_helper import DebugHelper

    # 测试参数：从参数或命令行获取
    if repo_path is None:
        if len(sys.argv) > 1:
            repo_path = sys.argv[1]
        else:
            print("❌ 错误: 请提供仓库路径作为参数")
            print("   用法: python structure_scanner_agent.py <repo_path>")
            return

    if not repo_path or not Path(repo_path).exists():
        print(f"❌ 错误: 仓库路径不存在: {repo_path}")
        return

    print("=" * 60)
    print("🧪 结构扫描 Agent 独立测试")
    print("=" * 60)

    # 创建 Debug Helper
    debug_helper = DebugHelper(enabled=True)

    # 创建扫描 Agent（Agent 内部会创建 client）
    scanner = StructureScannerAgent(debug_helper)

    try:
        # 执行扫描（Agent 会自动连接和设置权限）
        structure = await scanner.scan_repository(repo_path)

        # 输出结果摘要
        print("\n" + "=" * 60)
        print("📊 扫描结果摘要")
        print("=" * 60)

        project_info = structure.get('project_info', {})
        print(f"\n项目名称: {project_info.get('name')}")
        print(f"主要语言: {project_info.get('primary_language')}")
        print(f"文件总数: {project_info.get('total_files')}")

        modules = structure.get('modules', [])
        print(f"\n识别模块数: {len(modules)}")

        for i, module in enumerate(modules[:5], 1):  # 只显示前5个
            print(f"\n{i}. {module.get('name')}")
            print(f"   层次: {module.get('layer_guess', 'N/A')}")
            print(f"   职责: {module.get('responsibility', 'N/A')}")
            print(f"   文件数: {len(module.get('all_files', []))}")
            print(f"   关键文件: {len(module.get('key_files_paths', []))}")

        if len(modules) > 5:
            print(f"\n   ... 还有 {len(modules) - 5} 个模块")

        print("\n✅ 测试完成！详细结果已保存到 output/debug/ 目录")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scanner.disconnect()


if __name__ == "__main__":
    import asyncio
    # 从命令行参数读取仓库路径
    asyncio.run(test_scanner())

