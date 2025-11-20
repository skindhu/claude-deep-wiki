"""
Structure Validator - 结构扫描验证器

负责验证结构扫描结果的完整性，识别和修复孤立文件
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from utils.claude_query_helper import ClaudeQueryHelper
from utils.structure_prompt_builder import StructurePromptBuilder


class StructureValidator:
    """结构扫描验证器"""

    def __init__(self, client=None, prompt_builder: Optional[StructurePromptBuilder] = None):
        """
        初始化验证器

        Args:
            client: Claude SDK Client（用于智能修复）
            prompt_builder: StructurePromptBuilder 实例
        """
        self.client = client
        self.prompt_builder = prompt_builder
        self.claude_helper = ClaudeQueryHelper()
        self.last_response = None  # 保存最后一次 Claude 调用的原始响应

    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        规范化文件路径，确保路径格式一致

        Args:
            path: 原始路径

        Returns:
            规范化后的路径
        """
        if not path:
            return ""

        # 去除前导 ./
        path = path.lstrip('./')

        # 统一使用正斜杠
        path = path.replace('\\', '/')

        # 去除尾部斜杠
        path = path.rstrip('/')

        return path

    def validate_file_coverage(
        self,
        structure_overview: Dict[str, Any],
        repo_path: str,
        include_sub_modules: bool = False
    ) -> Dict[str, Any]:
        """
        验证文件覆盖率，识别遗漏的文件

        ⚠️ 阶段1/2简化版：默认只验证一级模块，不递归 sub_modules
        ⚠️ 阶段4完整版：可设置 include_sub_modules=True 递归验证所有子模块

        Args:
            structure_overview: 结构概览
            repo_path: 仓库路径
            include_sub_modules: 是否递归收集 sub_modules 的文件（默认 False）

        Returns:
            {
                "total_scanned": int,
                "total_in_modules": int,
                "orphan_files": [...],
                "coverage_rate": float,
                "scan_result": {...}
            }
        """
        # 获取完整的文件扫描列表
        from mcp_servers.code_analysis_server import scan_repository_structure

        scan_result = scan_repository_structure(repo_path)

        if not scan_result.get('success'):
            return {
                "total_scanned": 0,
                "total_in_modules": 0,
                "orphan_files": [],
                "coverage_rate": 0.0,
                "scan_result": scan_result
            }

        # 收集扫描到的所有文件路径（scan_repository_structure 已过滤，只有源码和配置文件）
        # 路径规范化：去除前导 ./ 并统一使用正斜杠
        scanned_files = {
            self._normalize_path(f['path'])
            for f in scan_result.get('files', [])
        }

        # 收集模块中的所有文件
        module_files = set()
        duplicate_files = []  # 记录重复分配的文件
        modules = structure_overview.get('modules', [])

        for module in modules:
            module_name = module.get('name', 'Unknown')

            # 收集一级模块的 all_files
            all_files = module.get('all_files')
            if all_files:  # 确保不是 None
                for file_path in all_files:
                    if file_path:  # 确保路径不为空
                        normalized = self._normalize_path(file_path)
                        if normalized in module_files:
                            duplicate_files.append(f"{file_path} (在 {module_name} 中)")
                        module_files.add(normalized)

            # 如果需要，递归收集 sub_modules 的文件
            if include_sub_modules:
                sub_modules = module.get('sub_modules', [])
                for sub_module in sub_modules:
                    sub_module_name = sub_module.get('name', 'Unknown')
                    sub_files = sub_module.get('all_files')
                    if sub_files:
                        for file_path in sub_files:
                            if file_path:
                                normalized = self._normalize_path(file_path)
                                if normalized in module_files:
                                    duplicate_files.append(f"{file_path} (在 {module_name}.{sub_module_name} 中)")
                                module_files.add(normalized)

        # 如果发现重复文件，警告
        if duplicate_files:
            print(f"     ⚠️  警告：发现 {len(duplicate_files)} 个重复分配的文件")
            for dup in duplicate_files[:5]:  # 只显示前5个
                print(f"        - {dup}")

        # 识别孤立文件（只在代码文件中查找）
        orphan_file_paths = scanned_files - module_files

        # 构建孤立文件详细信息（scan_repository_structure 已过滤）
        orphan_files = []
        for file_info in scan_result.get('files', []):
            normalized_path = self._normalize_path(file_info['path'])
            if normalized_path in orphan_file_paths:
                orphan_files.append(file_info)

        # 计算覆盖率（源码 + 配置文件）
        total_scanned = len(scanned_files)
        total_in_modules = len(module_files)
        coverage_rate = total_in_modules / total_scanned if total_scanned > 0 else 0.0

        return {
            "total_scanned": total_scanned,
            "total_in_modules": total_in_modules,
            "orphan_files": orphan_files,
            "coverage_rate": coverage_rate,
            "scan_result": scan_result
        }

    def _batch_orphan_files_by_tokens(
        self,
        orphan_files: List[Dict[str, Any]],
        max_tokens_per_batch: int = 40000,
        max_files_per_batch: int = 200
    ) -> List[List[Dict[str, Any]]]:
        """
        按 token 和文件数量限制分批孤立文件

        Args:
            orphan_files: 孤立文件列表
            max_tokens_per_batch: 每批的最大 token 数（默认 40k）
            max_files_per_batch: 每批的最大文件数（默认 200）

        Returns:
            分批后的文件列表
        """
        from utils.token_counter import count_tokens
        import json

        batches = []
        current_batch = []
        current_tokens = 0

        for file_info in orphan_files:
            # 简化文件信息，只保留必要字段以减少 token
            simplified_info = {
                'path': file_info.get('path'),
                'language': file_info.get('language'),
                'category': file_info.get('category')
            }

            # 计算单个文件信息的 token 数
            file_json = json.dumps(simplified_info, ensure_ascii=False)
            file_tokens = count_tokens(file_json)

            # 如果加入当前批次会超限（token 或文件数量），开始新批次
            if current_batch and (
                current_tokens + file_tokens > max_tokens_per_batch or
                len(current_batch) >= max_files_per_batch
            ):
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(file_info)
            current_tokens += file_tokens

        # 添加最后一批
        if current_batch:
            batches.append(current_batch)

        return batches

    async def fix_orphan_files_with_claude(
        self,
        structure_overview: Dict[str, Any],
        orphan_files: List[Dict[str, Any]],
        repo_path: str
    ) -> Dict[str, Any]:
        """
        使用 Claude 智能分析并修复孤立文件（支持分批处理）

        Args:
            structure_overview: 当前模块结构
            orphan_files: 孤立文件列表
            repo_path: 仓库路径

        Returns:
            更新后的 structure_overview
        """
        if not orphan_files:
            return structure_overview

        # 按 token 和文件数量限制分批
        batches = self._batch_orphan_files_by_tokens(
            orphan_files,
            max_tokens_per_batch=40000,
            max_files_per_batch=400
        )
        total_batches = len(batches)

        # 打印分批信息
        print(f"        📦 分批处理: 共 {len(orphan_files)} 个孤立文件，分为 {total_batches} 批")
        print(f"           限制: 每批最多 200 个文件 或 40k tokens")
        for i, batch in enumerate(batches, 1):
            print(f"           批次 {i}: {len(batch)} 个文件")

        # 收集所有批次的 assignments
        all_assignments = []
        total_tokens = 0

        from utils.token_counter import count_tokens

        # 逐批处理
        for batch_idx, batch in enumerate[List[Dict[str, Any]]](batches, 1):
            print(f"        → 处理批次 {batch_idx}/{total_batches}...")

            # 构建该批的提示词
            prompt = self.prompt_builder.build_orphan_files_fix_prompt(
                structure_overview.get('modules', []),
                batch,
                repo_path
            )

            # 统计当前批次的 token 数量
            batch_tokens = count_tokens(prompt)
            total_tokens += batch_tokens
            print(f"           🎯 批次 {batch_idx} Token: {batch_tokens:,} tokens")

            # 定义 validator：确保分配的文件数量和当前批次的孤立文件数量相近
            def validate_assignments(result, current_batch=batch):
                if not result or not result.get('assignments'):
                    return False

                assignments = result.get('assignments', [])
                assigned_files = {a.get('file') for a in assignments if a.get('file')}
                batch_file_paths = {f['path'] for f in current_batch}

                # 检查覆盖率：至少要覆盖 90% 的当前批次文件
                coverage = len(assigned_files & batch_file_paths) / len(batch_file_paths) if batch_file_paths else 0
                if coverage < 0.9:
                    print(f"              ⚠️  批次 {batch_idx} 分配覆盖率不足: {coverage:.1%}，重试中...")
                    return False

                return True

            # 调用 Claude 进行智能分析（错误处理在 ClaudeQueryHelper 内部完成）
            response_text, fix_result = await ClaudeQueryHelper.query_with_json_retry(
                client=self.client,
                prompt=prompt,
                session_id=f"structure_scan_orphan_fix_batch_{batch_idx}",
                max_attempts=3,
                validator=validate_assignments
            )

            # 收集该批次的 assignments
            batch_assignments = fix_result.get('assignments', [])
            all_assignments.extend(batch_assignments)
            print(f"           ✓ 批次 {batch_idx} 完成: {len(batch_assignments)} 个分配")

        # 打印总计信息
        print(f"        📊 总计: {total_batches} 批次, {total_tokens:,} tokens, {len(all_assignments)} 个分配")

        # 统一应用所有修复建议
        structure_overview = self.apply_fix_assignments(
            structure_overview,
            all_assignments
        )

        return structure_overview

    def apply_fix_assignments(
        self,
        structure_overview: Dict[str, Any],
        assignments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        应用 Claude 的修复建议

        Args:
            structure_overview: 当前结构
            assignments: Claude 的分配建议

        Returns:
            更新后的结构
        """
        modules = structure_overview.get('modules', [])

        # 统计各种操作
        assigned_count = 0
        new_modules_count = 0
        other_count = 0

        for assignment in assignments:
            action = assignment.get('action')
            file_path = assignment.get('file')

            if not file_path:
                continue

            if action == 'assign_to_existing':
                # 分配到现有模块
                target_module = assignment.get('target_module')
                for module in modules:
                    if module.get('name') == target_module:
                        if 'all_files' not in module:
                            module['all_files'] = []
                        # 检查文件是否已存在（考虑路径规范化）
                        normalized_existing = [self._normalize_path(f) for f in module['all_files']]
                        if self._normalize_path(file_path) not in normalized_existing:
                            module['all_files'].append(file_path)
                        assigned_count += 1
                        break

            elif action == 'create_new_module':
                # 创建新模块
                new_module = assignment.get('new_module', {})
                if new_module:
                    # 确保新模块有必要的字段
                    if 'all_files' not in new_module:
                        new_module['all_files'] = []
                    if 'key_files_paths' not in new_module:
                        new_module['key_files_paths'] = []
                    if 'sub_modules' not in new_module:
                        new_module['sub_modules'] = []
                    modules.append(new_module)
                    new_modules_count += 1

            elif action == 'assign_to_other':
                # 归入"其他文件"模块
                other_module = self.get_or_create_other_module(modules)
                # 检查文件是否已存在（考虑路径规范化）
                normalized_existing = [self._normalize_path(f) for f in other_module['all_files']]
                if self._normalize_path(file_path) not in normalized_existing:
                    other_module['all_files'].append(file_path)
                other_count += 1

        # 打印修复摘要
        if assigned_count > 0:
            print(f"        ✓ 分配到现有模块: {assigned_count} 个文件")
        if new_modules_count > 0:
            print(f"        ✓ 创建新模块: {new_modules_count} 个")
        if other_count > 0:
            print(f"        ✓ 归入其他文件: {other_count} 个文件")

        structure_overview['modules'] = modules
        return structure_overview

    @staticmethod
    def get_or_create_other_module(modules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取或创建"其他文件"模块

        Args:
            modules: 模块列表

        Returns:
            "其他文件"模块
        """
        # 查找是否已存在
        for module in modules:
            if module.get('name') == '其他文件':
                return module

        # 创建新的"其他文件"模块
        other_module = {
            "name": "其他文件",
            "layer_guess": "utils",
            "responsibility": "未分类的配置文件、脚本和其他辅助文件",
            "all_files": [],
            "key_files_paths": [],
            "sub_modules": []
        }
        modules.append(other_module)
        return other_module

    def _collect_all_files(self, structure_overview: Dict[str, Any]) -> List[str]:
        """
        收集结构中的所有文件（用于计算总文件数）

        递归收集所有模块和子模块中的文件

        Args:
            structure_overview: 结构概览

        Returns:
            所有文件路径列表
        """
        all_files = []

        def collect_from_module(module):
            all_files.extend(module.get('all_files', []))
            for sub in module.get('sub_modules', []):
                collect_from_module(sub)

        for module in structure_overview.get('modules', []):
            collect_from_module(module)

        return all_files

    def detect_large_modules(
        self,
        structure_overview: Dict[str, Any],
        relative_threshold: float = 0.10,  # 相对阈值：20%
        min_threshold: int = 5,           # 绝对下限
        max_threshold: int = 30           # 绝对上限
    ) -> List[Dict[str, Any]]:
        """
        检测需要细分的大模块（综合判断策略）

        策略：
        1. 计算相对阈值（总文件数 * relative_threshold）
        2. 限制在 [min_threshold, max_threshold] 范围内
        3. 文件数 > 阈值的模块需要细分

        Args:
            structure_overview: 结构概览
            relative_threshold: 相对阈值（默认 0.20，即 20%）
            min_threshold: 绝对下限（默认 20 文件）
            max_threshold: 绝对上限（默认 60 文件）

        Returns:
            需要细分的大模块列表
        """
        # 计算总文件数
        total_files = len(self._collect_all_files(structure_overview))

        # 计算动态阈值
        threshold = int(total_files * relative_threshold)
        threshold = max(min_threshold, min(threshold, max_threshold))

        print(f"        📊 细分策略: 阈值 = {threshold} 文件")
        print(f"           （总文件: {total_files}, 相对: {relative_threshold*100:.0f}%, 范围: [{min_threshold}, {max_threshold}]）")

        large_modules = []

        def check_module(module, parent_path=[]):
            file_count = len(module.get('all_files', []))
            if file_count > threshold:
                large_modules.append({
                    "module_path": parent_path + [module['name']],
                    "module_name": module['name'],
                    "file_count": file_count,
                    "all_files": module['all_files'],
                    "module_ref": module,
                    "threshold": threshold
                })

            # 递归检查子模块
            for sub in module.get('sub_modules', []):
                check_module(sub, parent_path + [module['name']])

        for module in structure_overview.get('modules', []):
            check_module(module)

        return large_modules

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 阶段3：大模块智能细分的新方法
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def plan_module_subdivision(
        self,
        large_module: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        阶段3.1：规划子模块细分（只规划，不分配所有文件）

        Args:
            large_module: 大模块信息 {
                'module_name': str,
                'module_path': List[str],
                'module_ref': Dict,
                'file_count': int,
                'all_files': List[str]
            }

        Returns:
            子模块规划列表 [
                {
                    'name': str,
                    'description': str,
                    'suggested_key_files': List[str],
                    'suggested_entry_files': List[str]
                },
                ...
            ]
        """
        print(f"        → 3.1: 规划子模块...")

        # 构建 prompt
        prompt = self.prompt_builder.build_module_subdivision_planning_prompt(
            module_info=large_module,
            repo_path=self._get_repo_path()
        )

        # 验证器：检查规划结果的结构
        all_files_set = set(large_module['all_files'])

        def validate_planning(result):
            if not result or not isinstance(result, dict):
                return False

            sub_modules = result.get('sub_modules', [])
            if not sub_modules or not isinstance(sub_modules, list):
                print(f"           ⚠️  缺少 sub_modules 字段或格式错误")
                return False

            if len(sub_modules) < 1:
                print(f"           ⚠️  子模块数量不合理: {len(sub_modules)}（建议 1-15 个）")
                return False

            for idx, sub in enumerate(sub_modules, 1):
                # 检查必需字段
                if not sub.get('name'):
                    print(f"           ⚠️  子模块 {idx} 缺少 name 字段")
                    return False

                if not sub.get('description'):
                    print(f"           ⚠️  子模块 {idx} ({sub['name']}) 缺少 description 字段")
                    return False

                # 检查建议的文件路径是否存在
                suggested_key = sub.get('suggested_key_files', [])
                suggested_entry = sub.get('suggested_entry_files', [])

                if not suggested_key and not suggested_entry:
                    print(f"           ⚠️  子模块 {idx} ({sub['name']}) 没有建议任何关键文件")
                    return False

            return True

        # 调用 Claude 获取规划（使用固化的 session_id 保持上下文连贯）
        response_text, result = await self.claude_helper.query_with_json_retry(
            client=self.client,
            prompt=prompt,
            session_id="subdivision_planning",
            max_attempts=3,
            validator=validate_planning
        )

        # 保存原始响应
        self.last_response = response_text

        subdivision_plan = result.get('sub_modules', [])

        print(f"           ✓ 规划完成，共 {len(subdivision_plan)} 个子模块")
        for idx, sub in enumerate(subdivision_plan, 1):
            key_count = len(sub.get('suggested_key_files', []))
            entry_count = len(sub.get('suggested_entry_files', []))
            print(f"              {idx}. {sub['name']} (key:{key_count}, entry:{entry_count})")

        return subdivision_plan

    async def assign_files_by_dependency(
        self,
        parent_module: Dict[str, Any],
        subdivision_plan: List[Dict[str, Any]],
        repo_path: str
    ) -> List[Dict[str, Any]]:
        """
        阶段3.2：依赖驱动的文件归属（自动分配 + 循环依赖处理）

        Args:
            parent_module: 父模块信息
            subdivision_plan: 子模块规划
            repo_path: 仓库根路径

        Returns:
            带有 all_files 的子模块列表
        """
        print(f"        → 3.2: 依赖驱动的文件归属...")

        # 初始化依赖分析器
        from utils.dependency_analyzer import (
            DependencyAnalyzer,
            resolve_circular_conflicts
        )
        analyzer = DependencyAnalyzer()

        # 步骤1：构建依赖图
        all_files = parent_module['all_files']
        dependency_graph = analyzer.build_dependency_graph(all_files, repo_path)

        # 步骤2：检测循环依赖
        circular_groups = analyzer.detect_circular_dependencies(dependency_graph)

        # 步骤3：为每个子模块初步收集文件
        module_base_path = self._extract_module_base_path(parent_module)

        for sub_module in subdivision_plan:
            # 合并 suggested_entry_files 和 suggested_key_files 作为起点
            start_files = list(set(
                sub_module.get('suggested_entry_files', []) +
                sub_module.get('suggested_key_files', [])
            ))

            # BFS 遍历依赖
            code_files = await analyzer.traverse_dependencies(
                start_files=start_files,
                dependency_graph=dependency_graph,
                max_depth=20,
                scope_pattern=module_base_path
            )

            # 初步文件列表
            sub_module['preliminary_files'] = list(code_files)

            print(f"           • {sub_module['name']}: {len(code_files)} 个文件（依赖遍历）")

        # 步骤4：解决循环依赖冲突
        if circular_groups:
            resolve_circular_conflicts(
                sub_modules=subdivision_plan,
                circular_groups=circular_groups,
                dependency_graph=dependency_graph
            )

        # 步骤5：补充配置/资源文件（路径匹配）
        assigned_files = set()
        for sub_module in subdivision_plan:
            assigned_files.update(sub_module['preliminary_files'])

        orphan_files = [f for f in all_files if f not in assigned_files]

        print(f"           ℹ️  依赖遍历后剩余 {len(orphan_files)} 个未分配文件")

        # for sub_module in subdivision_plan:
        #     # 根据路径关键词匹配配置文件
        #     config_files = analyzer.match_config_files_by_path(
        #         sub_module_name=sub_module['name'],
        #         orphan_files=orphan_files,
        #         module_base_path=module_base_path
        #     )

        #     if config_files:
        #         sub_module['preliminary_files'].extend(config_files)
        #         assigned_files.update(config_files)
        #         print(f"           • {sub_module['name']}: +{len(config_files)} 个配置文件（路径匹配）")

        # 步骤6：按依赖顺序排序并清理字段
        for sub_module in subdivision_plan:
            # 使用拓扑排序
            preliminary_files_list = list(sub_module.pop('preliminary_files'))
            sub_module['all_files'] = analyzer.topological_sort_files(
                preliminary_files_list,
                dependency_graph
            )

            # 移除临时字段
            sub_module.pop('suggested_key_files', None)
            sub_module.pop('suggested_entry_files', None)

        print(f"           ✓ 文件归属完成")

        return subdivision_plan

    async def verify_subdivision_with_claude(
        self,
        parent_module: Dict[str, Any],
        auto_assigned_sub_modules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        阶段3.3：处理未分配文件，将其保留在父模块

        未分配的文件（没有依赖关系）直接归属于一级模块本身，
        这些通常是入口文件或全局配置文件。

        Args:
            parent_module: 父模块信息（会被原地修改，更新 all_files）
            auto_assigned_sub_modules: 自动分配后的子模块列表

        Returns:
            自动分配的子模块列表（不做修改）
        """
        print(f"        → 3.3: 处理未分配文件...")

        # 计算遗漏文件
        assigned_files = set()
        for sub in auto_assigned_sub_modules:
            assigned_files.update(sub.get('all_files', []))
        parent_files = set(parent_module['all_files'])
        missing_files = parent_files - assigned_files

        # 更新父模块的 all_files
        # 需要同时更新 large_module 和 module_ref（如果存在）
        if not missing_files:
            missing_files_list = []
            parent_module['all_files'] = []
            # 如果存在 module_ref，同步更新原始模块的 all_files
            if 'module_ref' in parent_module:
                parent_module['module_ref']['all_files'] = []
            print(f"           ✓ 所有文件已分配到子模块")
        else:
            # 按文件路径排序，保证结果一致性
            missing_files_list = sorted(list(missing_files))
            parent_module['all_files'] = missing_files_list
            # 如果存在 module_ref，同步更新原始模块的 all_files
            if 'module_ref' in parent_module:
                parent_module['module_ref']['all_files'] = missing_files_list
            print(f"           ✓ {len(missing_files)} 个文件保留在父模块（入口文件等）")

        # 直接返回自动分配的子模块列表
        return auto_assigned_sub_modules

    def _extract_module_base_path(self, module_info: Dict[str, Any]) -> str:
        """
        提取模块的基础路径

        Args:
            module_info: 模块信息

        Returns:
            模块基础路径（如 "app_cf/lib/cf_game/"）
        """
        # 从 all_files 中提取公共前缀
        all_files = module_info.get('all_files', [])
        if not all_files:
            return ''

        # 找出所有文件的公共路径前缀
        import os
        common_prefix = os.path.commonprefix(all_files)

        # 确保以目录分隔符结尾
        if common_prefix and not common_prefix.endswith('/'):
            # 找到最后一个 '/' 之前的部分
            common_prefix = common_prefix.rsplit('/', 1)[0] + '/'

        return common_prefix

    def _get_repo_path(self) -> str:
        """
        获取仓库路径（从某个地方获取，这里简化处理）

        Returns:
            仓库路径
        """
        # TODO: 从配置或上下文获取
        # 这里暂时返回占位符，实际使用时需要传入
        return "/path/to/repo"

