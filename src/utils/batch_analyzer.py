"""
文件分析批处理管理器

职责：
1. Token估算（读取文件计算大小）
2. 文件依赖关系提取（直接调用函数，不通过Claude）
3. 基于关联度的智能分批
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import deque

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.code_analysis_server import extract_imports_and_exports
from mcp_tools.language_detector import get_language_detector
from config import BATCH_MAX_TOKENS, TOKENS_PER_CHAR, PROMPT_RESERVED_TOKENS


class FileAnalysisBatchManager:
    """文件分析批处理管理器"""

    def __init__(self, repo_path: str):
        """
        初始化批处理管理器

        Args:
            repo_path: 仓库根目录路径
        """
        self.repo_path = Path(repo_path)
        self.file_tokens = {}  # 缓存token估算
        self.language_detector = get_language_detector()

    def estimate_file_tokens(self, file_path: str) -> int:
        """
        估算文件的token数

        Args:
            file_path: 文件路径（相对或绝对）

        Returns:
            估算的token数
        """
        if file_path in self.file_tokens:
            return self.file_tokens[file_path]

        try:
            abs_path = self.repo_path / file_path if not Path(file_path).is_absolute() else Path(file_path)
            content = abs_path.read_text(encoding='utf-8')
            tokens = int(len(content) * TOKENS_PER_CHAR)
            self.file_tokens[file_path] = tokens
            return tokens
        except Exception as e:
            # 文件读取失败，返回默认值
            print(f"      ⚠️ 读取文件失败: {file_path} - {str(e)}")
            return 1000

    def prepare_files_with_dependencies(
        self, all_files: List[str], key_files: List[Dict]
    ) -> List[Dict]:
        """
        准备文件信息（混合复用和直接函数调用）

        策略：
        1. key_files: 直接复用已有的 imports/exports
        2. 其他文件: 直接调用 extract_imports_and_exports 函数（本地调用，很快）

        Args:
            all_files: 所有文件路径列表
            key_files: 关键文件信息列表（已包含imports/exports）

        Returns:
            准备好的文件信息列表
        """
        # 1. 创建 key_files 映射
        key_file_map = {kf['path']: kf for kf in key_files}

        # 2. 准备所有文件
        prepared_files = []
        files_need_extraction = [f for f in all_files if f not in key_file_map]

        print(f"    准备文件: {len(all_files)}个文件 ({len(key_files)}个复用, {len(files_need_extraction)}个需提取)")

        # 3. 处理所有文件
        for idx, file_path in enumerate(all_files, 1):
            if file_path in key_file_map:
                # 复用 key_file
                prepared_files.append(key_file_map[file_path])
            else:
                # 直接调用函数提取依赖（本地调用，速度快）
                try:
                    result = extract_imports_and_exports(
                        file_path=file_path,
                        repo_root=str(self.repo_path)
                    )

                    if result.get('success'):
                        # 简化imports格式（只保留模块名）
                        imports = []
                        for imp in result.get('imports', []):
                            if isinstance(imp, dict):
                                imports.append(imp.get('module', ''))
                            else:
                                imports.append(str(imp))

                        prepared_files.append({
                            'path': file_path,
                            'imports': imports,
                            'exports': result.get('exports', []),
                            'language': result.get('language', 'unknown')
                        })
                    else:
                        # 提取失败，添加基本信息
                        error_msg = result.get('error', 'Unknown error')
                        print(f"      ⚠️ 提取失败: {file_path} - {error_msg}")
                        prepared_files.append({
                            'path': file_path,
                            'imports': [],
                            'exports': [],
                            'language': self._detect_language(file_path)
                        })
                except Exception as e:
                    # 异常，添加基本信息
                    print(f"      ⚠️ 提取异常: {file_path} - {str(e)}")
                    prepared_files.append({
                        'path': file_path,
                        'imports': [],
                        'exports': [],
                        'language': self._detect_language(file_path)
                    })

            # 进度提示（每10个文件）
            if idx % 10 == 0:
                print(f"      进度: {idx}/{len(all_files)} 个文件")

        return prepared_files

    def build_file_dependency_graph(self, files: List[Dict]) -> Dict:
        """
        构建文件依赖图

        Args:
            files: 文件信息列表

        Returns:
            {
                'adjacency_list': {file_path: [imported_files]},
                'reverse_deps': {file_path: [files_that_import_it]},
                'cohesion_matrix': {(file_a, file_b): score}
            }
        """
        adjacency_list = {}
        reverse_deps = {}

        # 创建路径映射
        file_paths = {f['path'] for f in files}
        file_dirs = {f['path']: str(Path(f['path']).parent) for f in files}

        # 构建依赖图
        for file_info in files:
            file_path = file_info['path']
            imports = file_info.get('imports', [])

            adjacency_list[file_path] = []

            for import_str in imports:
                # 解析导入路径，转换为项目内的绝对路径
                resolved_path = self._resolve_import_path(import_str, file_path, file_paths)

                if resolved_path and resolved_path in file_paths:
                    adjacency_list[file_path].append(resolved_path)

                    if resolved_path not in reverse_deps:
                        reverse_deps[resolved_path] = []
                    reverse_deps[resolved_path].append(file_path)

        # 计算关联度矩阵
        cohesion_matrix = self._calculate_cohesion_matrix(
            files, adjacency_list, reverse_deps, file_dirs
        )

        return {
            'adjacency_list': adjacency_list,
            'reverse_deps': reverse_deps,
            'cohesion_matrix': cohesion_matrix
        }

    def create_file_batches(self, files: List[Dict]) -> List[Dict]:
        """
        基于关联度和token限制创建批次

        算法：
        1. 估算所有文件的token
        2. 构建依赖图
        3. 识别强连通组件（紧密关联的文件组）
        4. 按关联度分批，控制每批token数

        Args:
            files: 文件信息列表

        Returns:
            批次列表
        """
        # 1. 估算token
        print(f"    步骤1: 估算文件大小...")
        for file_info in files:
            file_info['estimated_tokens'] = self.estimate_file_tokens(file_info['path'])

        # 2. 构建依赖图
        print(f"    步骤2: 构建依赖图...")
        dep_graph = self.build_file_dependency_graph(files)

        # 3. 识别强连通组件
        print(f"    步骤3: 识别文件关联组...")
        components = self._find_connected_components(dep_graph['adjacency_list'], files)

        # 4. 按token限制分批
        print(f"    步骤4: 创建批次...")
        batches = []
        available_tokens = BATCH_MAX_TOKENS - PROMPT_RESERVED_TOKENS

        for component in components:
            component_files = [f for f in files if f['path'] in component]

            # 按依赖顺序排序（被依赖的在前）
            sorted_files = self._sort_by_dependency(
                component_files, dep_graph['reverse_deps']
            )

            # 分批
            current_batch = []
            current_tokens = 0

            for file_info in sorted_files:
                file_tokens = file_info['estimated_tokens']

                # 单个文件太大，单独成批
                if file_tokens > available_tokens:
                    if current_batch:
                        batches.append(self._create_batch_info(current_batch, dep_graph))
                        current_batch = []
                        current_tokens = 0

                    batches.append(self._create_batch_info([file_info], dep_graph))
                    continue

                if current_tokens + file_tokens > available_tokens and current_batch:
                    # 当前批次已满，创建新批次
                    batches.append(self._create_batch_info(current_batch, dep_graph))
                    current_batch = []
                    current_tokens = 0

                current_batch.append(file_info)
                current_tokens += file_tokens

            # 添加最后一个批次
            if current_batch:
                batches.append(self._create_batch_info(current_batch, dep_graph))

        # 5. 优化批次：合并小批次
        print(f"    步骤5: 优化批次（合并小批次）...")
        optimized_batches = self._optimize_batches(batches, available_tokens)

        print(f"    ✅ 批次创建完成: {len(components)} 个组件 → "
              f"{len(batches)} 个初始批次 → {len(optimized_batches)} 个优化批次")

        return optimized_batches

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _detect_language(self, file_path: str) -> str:
        """检测文件语言"""
        try:
            return self.language_detector.detect_language(Path(file_path))
        except:
            return 'unknown'

    def _resolve_import_path(
        self, import_str: str, from_file: str, all_file_paths: Set[str]
    ) -> str:
        """
        解析导入路径为项目内的绝对路径

        Args:
            import_str: 导入字符串
            from_file: 导入的源文件
            all_file_paths: 所有文件路径集合

        Returns:
            解析后的路径，如果不在项目内则返回None
        """
        # 处理相对导入
        if import_str.startswith('./') or import_str.startswith('../'):
            from_dir = Path(from_file).parent
            try:
                resolved = (from_dir / import_str).resolve()
                rel_path = str(resolved.relative_to(self.repo_path))

                # 尝试添加扩展名
                for ext in ['', '.js', '.ts', '.jsx', '.tsx', '.vue', '.py', '.java']:
                    candidate = rel_path + ext
                    if candidate in all_file_paths:
                        return candidate
            except:
                pass

        # 处理别名导入（如 @/）
        if import_str.startswith('@/'):
            rel_import = import_str[2:]  # 移除 @/

            # 尝试不同的扩展名
            for ext in ['', '.js', '.ts', '.jsx', '.tsx', '.vue', '.py']:
                candidate = f"src/{rel_import}{ext}"
                if candidate in all_file_paths:
                    return candidate

        return None

    def _calculate_cohesion_matrix(
        self,
        files: List[Dict],
        adjacency_list: Dict,
        reverse_deps: Dict,
        file_dirs: Dict
    ) -> Dict[Tuple[str, str], float]:
        """
        计算文件间关联度矩阵

        权重：
        - 直接依赖：5
        - 间接依赖：3
        - 同目录：2
        """
        cohesion_matrix = {}
        file_paths = [f['path'] for f in files]

        for i, file_a in enumerate(file_paths):
            for j, file_b in enumerate(file_paths):
                if i >= j:
                    continue

                score = 0

                # 直接依赖
                if file_b in adjacency_list.get(file_a, []):
                    score += 5
                if file_a in adjacency_list.get(file_b, []):
                    score += 5

                # 间接依赖（共同导入）
                imports_a = set(adjacency_list.get(file_a, []))
                imports_b = set(adjacency_list.get(file_b, []))
                common_imports = len(imports_a & imports_b)
                score += common_imports * 3

                # 同目录
                if file_dirs.get(file_a) == file_dirs.get(file_b):
                    score += 2

                if score > 0:
                    cohesion_matrix[(file_a, file_b)] = score
                    cohesion_matrix[(file_b, file_a)] = score

        return cohesion_matrix

    def _find_connected_components(
        self, adjacency_list: Dict, files: List[Dict]
    ) -> List[Set[str]]:
        """
        使用BFS查找连通组件

        Args:
            adjacency_list: 邻接表
            files: 文件列表

        Returns:
            连通组件列表（每个组件是文件路径集合）
        """
        visited = set()
        components = []
        file_paths = [f['path'] for f in files]

        for file_path in file_paths:
            if file_path in visited:
                continue

            # BFS查找连通组件
            component = set()
            queue = deque([file_path])

            while queue:
                current = queue.popleft()
                if current in visited:
                    continue

                visited.add(current)
                component.add(current)

                # 添加所有相关文件（导入和被导入）
                for neighbor in adjacency_list.get(current, []):
                    if neighbor not in visited:
                        queue.append(neighbor)

            components.append(component)

        # 按组件大小排序（大的在前）
        components.sort(key=len, reverse=True)

        return components

    def _sort_by_dependency(
        self, files: List[Dict], reverse_deps: Dict
    ) -> List[Dict]:
        """
        按依赖顺序排序文件（被依赖的在前）

        Args:
            files: 文件列表
            reverse_deps: 反向依赖图

        Returns:
            排序后的文件列表
        """
        # 简单策略：按被依赖次数排序
        files_with_score = []
        for file_info in files:
            dep_count = len(reverse_deps.get(file_info['path'], []))
            files_with_score.append((file_info, dep_count))

        # 被依赖多的在前
        files_with_score.sort(key=lambda x: x[1], reverse=True)

        return [f[0] for f in files_with_score]

    def _optimize_batches(
        self, batches: List[Dict], available_tokens: int
    ) -> List[Dict]:
        """
        优化批次：合并小批次以提高 token 利用率

        策略：直接合并小批次（< 30% 可用容量），确保不超过 token 限制

        Args:
            batches: 初始批次列表
            available_tokens: 可用 token 数

        Returns:
            优化后的批次列表
        """
        if len(batches) <= 1:
            return batches

        # 定义"小批次"的阈值（30% 可用容量）
        small_batch_threshold = available_tokens * 0.3

        # 分离大批次和小批次
        large_batches = []
        small_batches = []

        for batch in batches:
            if batch['estimated_tokens'] > small_batch_threshold:
                large_batches.append(batch)
            else:
                small_batches.append(batch)

        if len(small_batches) <= 1:
            # 没有足够的小批次需要合并
            return batches

        print(f"      发现 {len(small_batches)} 个小批次（< {int(small_batch_threshold)} tokens），尝试合并...")

        # 直接合并小批次
        merged_batches = []
        current_merged = {
            'files': [],
            'estimated_tokens': 0,
            'cohesion': 0.0,
            'description': '合并批次'
        }

        for batch in small_batches:
            batch_tokens = batch['estimated_tokens']

            # 检查是否可以合并到当前批次
            if current_merged['estimated_tokens'] + batch_tokens <= available_tokens:
                # 合并
                current_merged['files'].extend(batch['files'])
                current_merged['estimated_tokens'] += batch_tokens
            else:
                # 当前批次已满，保存并开始新批次
                if current_merged['files']:
                    merged_batches.append(current_merged)

                # 开始新批次
                current_merged = {
                    'files': batch['files'].copy(),
                    'estimated_tokens': batch_tokens,
                    'cohesion': batch['cohesion'],
                    'description': '合并批次'
                }

        # 添加最后一个合并批次
        if current_merged['files']:
            merged_batches.append(current_merged)

        # 合并大批次和优化后的小批次
        final_batches = large_batches + merged_batches

        # 按 token 数排序（大的在前，便于调试查看）
        final_batches.sort(key=lambda b: b['estimated_tokens'], reverse=True)

        print(f"      合并完成: {len(small_batches)} → {len(merged_batches)} 个批次")

        return final_batches

    def _create_batch_info(
        self, files: List[Dict], dep_graph: Dict
    ) -> Dict:
        """
        创建批次信息

        Args:
            files: 批次中的文件列表
            dep_graph: 依赖图

        Returns:
            批次信息字典
        """
        total_tokens = sum(f.get('estimated_tokens', 1000) for f in files)

        # 计算关联度
        cohesion = self._calculate_batch_cohesion(files, dep_graph)

        # 生成描述
        file_paths = [f['path'] for f in files]
        common_dir = self._find_common_directory(file_paths)
        description = f"文件组: {common_dir}" if common_dir else "混合文件组"

        return {
            'files': files,
            'estimated_tokens': total_tokens,
            'cohesion': cohesion,
            'description': description
        }

    def _calculate_batch_cohesion(
        self, files: List[Dict], dep_graph: Dict
    ) -> float:
        """
        计算批次内的关联度

        Returns:
            关联度数值 (0.0 到 1.0)，值越大表示关联度越高
        """
        if len(files) <= 1:
            return 1.0

        file_paths = [f['path'] for f in files]
        adjacency_list = dep_graph['adjacency_list']

        # 计算批次内的依赖关系数量
        internal_deps = 0
        for file_path in file_paths:
            for imported in adjacency_list.get(file_path, []):
                if imported in file_paths:
                    internal_deps += 1

        # 计算关联度比例
        max_deps = len(files) * (len(files) - 1)
        if max_deps == 0:
            return 0.0

        ratio = internal_deps / max_deps
        return round(ratio, 2)

    def _find_common_directory(self, file_paths: List[str]) -> str:
        """
        查找文件的公共目录

        Args:
            file_paths: 文件路径列表

        Returns:
            公共目录路径
        """
        if not file_paths:
            return ''

        paths = [Path(p).parts for p in file_paths]
        common = []

        for parts in zip(*paths):
            if len(set(parts)) == 1:
                common.append(parts[0])
            else:
                break

        return '/'.join(common) if common else ''

