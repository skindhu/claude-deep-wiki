"""
Dependency Analyzer - 依赖分析器

负责分析代码文件之间的依赖关系，用于阶段3的智能模块细分。

核心功能：
1. 构建依赖图（文件 -> 导入的文件列表）
2. 检测循环依赖（强连通分量）
3. BFS遍历依赖关系
4. 解决循环依赖冲突
"""

from typing import Dict, List, Set, Any, Tuple
import os
import re
from pathlib import Path
from mcp_servers.code_analysis_server import extract_imports_and_exports


class DependencyAnalyzer:
    """依赖分析器，用于构建和分析代码依赖关系"""

    def __init__(self):
        """
        初始化依赖分析器
        """
        self.dependency_cache: Dict[str, List[str]] = {}  # 缓存依赖关系
        self.package_map: Dict[str, str] = {}  # Dart package 名称 -> lib 目录

    def build_dependency_graph(
        self,
        files: List[str],
        repo_path: str
    ) -> Dict[str, List[str]]:
        """
        构建完整依赖图：file -> [imported files]

        Args:
            files: 文件路径列表
            repo_path: 仓库根路径

        Returns:
            依赖图字典 {file_path: [imported_file1, imported_file2, ...]}
        """
        # 首次构建时扫描 Dart package 映射
        if not self.package_map:
            self.package_map = self._scan_dart_packages(repo_path)
            if self.package_map:
                print(f"        📦 检测到 {len(self.package_map)} 个 Dart 包")

        graph = {}

        print(f"        🔗 构建依赖图（共 {len(files)} 个文件）...")

        for i, file in enumerate(files):
            if (i + 1) % 50 == 0:
                print(f"           进度: {i + 1}/{len(files)}")

            imports = self._extract_imports(file, repo_path)
            graph[file] = imports

        print(f"        ✓ 依赖图构建完成")
        return graph

    def _extract_imports(self, file_path: str, repo_path: str) -> List[str]:
        """
        提取文件的导入依赖

        Args:
            file_path: 文件路径
            repo_path: 仓库根路径

        Returns:
            导入的文件路径列表
        """
        # 检查缓存
        if file_path in self.dependency_cache:
            return self.dependency_cache[file_path]

        try:
            # 直接调用函数提取导入
            result = extract_imports_and_exports(
                file_path=file_path,
                repo_root=repo_path
            )

            if result and result.get('success'):
                imports = result.get('imports', [])

                # 解析导入路径为文件路径
                imported_files = []
                for imp in imports:
                    source = imp.get('source', '')
                    if source:
                        # 解析相对路径为绝对路径
                        resolved = self._resolve_import_path(
                            source, file_path, repo_path
                        )
                        if resolved:
                            imported_files.append(resolved)

                # 缓存结果
                self.dependency_cache[file_path] = imported_files
                return imported_files

        except Exception as e:
            print(f"           ⚠️  提取 {file_path} 的导入失败: {e}")

        # 失败时返回空列表
        self.dependency_cache[file_path] = []
        return []

    def _scan_dart_packages(self, repo_path: str) -> Dict[str, str]:
        """
        扫描仓库中的 pubspec.yaml 文件，构建 Dart package 到 lib 目录的映射
        """
        package_map: Dict[str, str] = {}
        repo = Path(repo_path).resolve()

        if not repo.exists():
            return package_map

        try:
            pubspec_files = repo.rglob('pubspec.yaml')
        except Exception as e:
            print(f"           ⚠️  扫描 pubspec.yaml 失败: {e}")
            return package_map

        name_pattern = re.compile(r'^\s*name:\s*([^\s#]+)', re.MULTILINE)

        for pubspec in pubspec_files:
            try:
                content = pubspec.read_text(encoding='utf-8')
            except Exception:
                continue

            match = name_pattern.search(content)
            if not match:
                continue

            package_name = match.group(1).strip()
            if not package_name:
                continue

            lib_dir = pubspec.parent / 'lib'
            target_dir = lib_dir if lib_dir.exists() else pubspec.parent
            target_resolved = target_dir.resolve()

            if target_resolved.is_relative_to(repo):
                relative_path = target_resolved.relative_to(repo)
                package_map[package_name] = str(relative_path)
            else:
                package_map[package_name] = str(target_resolved)

        return package_map

    def _resolve_import_path(
        self,
        import_source: str,
        current_file: str,
        repo_path: str
    ) -> str:
        """
        解析导入路径为实际文件路径

        Args:
            import_source: 导入语句中的路径（如 ./utils, ../models/user）
            current_file: 当前文件路径
            repo_path: 仓库根路径

        Returns:
            解析后的文件路径，如果无法解析则返回空字符串
        """
        # 移除包装符号（引号等）
        import_source = import_source.strip('\'"')

        # 如果是相对导入
        if import_source.startswith('.'):
            # 获取当前文件所在目录
            current_dir = os.path.dirname(current_file)

            # 拼接路径
            resolved = os.path.normpath(
                os.path.join(current_dir, import_source)
            )

            if os.path.splitext(resolved)[1]:
                return resolved

            for ext in ('.dart', '.js', '.ts', '.py', '.java', '.go'):
                candidate = resolved + ext
                if os.path.exists(candidate):
                    return candidate

            return resolved

        # 处理 package: 导入
        if import_source.startswith('package:'):
            parts = import_source.replace('package:', '', 1).split('/', 1)
            package_name = parts[0]
            relative_path = parts[1] if len(parts) > 1 else ''

            lib_dir = self.package_map.get(package_name)
            if lib_dir and relative_path:
                resolved = os.path.normpath(os.path.join(lib_dir, relative_path))
                return resolved
            elif lib_dir:
                return lib_dir

            return ''

        # 处理未带前缀的路径（同目录或子目录）
        if not os.path.isabs(import_source):
            current_dir = os.path.dirname(current_file)
            resolved = os.path.normpath(os.path.join(current_dir, import_source))

            if os.path.splitext(resolved)[1]:
                return resolved

            dart_candidate = resolved + '.dart'
            if os.path.exists(dart_candidate):
                return dart_candidate

            return resolved

        return ''

    def detect_circular_dependencies(
        self,
        dependency_graph: Dict[str, List[str]]
    ) -> List[Set[str]]:
        """
        检测所有循环依赖组（强连通分量）

        使用 Tarjan 算法检测强连通分量

        Args:
            dependency_graph: 依赖图

        Returns:
            循环依赖组列表，每个元素是一个文件集合
        """
        print(f"        🔍 检测循环依赖...")

        sccs = self._tarjan_scc(dependency_graph)

        print(f"        ✓ 检测到 {len(sccs)} 个循环依赖组")
        for i, scc in enumerate(sccs[:3]):  # 只显示前3个
            print(f"           组 {i+1}: {len(scc)} 个文件")

        return sccs

    def _tarjan_scc(self, graph: Dict[str, List[str]]) -> List[Set[str]]:
        """
        Tarjan算法检测强连通分量（循环依赖组）

        Args:
            graph: 依赖图 {file: [imported_files]}

        Returns:
            强连通分量列表（每个大小>1表示有循环）
        """
        index_counter = [0]
        stack = []
        lowlinks = {}
        index = {}
        on_stack = {}
        sccs = []

        def strongconnect(node):
            # 设置节点的索引
            index[node] = index_counter[0]
            lowlinks[node] = index_counter[0]
            index_counter[0] += 1
            on_stack[node] = True
            stack.append(node)

            # 遍历后继节点
            for successor in graph.get(node, []):
                if successor not in index:
                    # 后继节点未访问，递归
                    strongconnect(successor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[successor])
                elif on_stack.get(successor, False):
                    # 后继节点在栈中，说明找到环
                    lowlinks[node] = min(lowlinks[node], index[successor])

            # 如果是强连通分量的根
            if lowlinks[node] == index[node]:
                scc = set()
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.add(w)
                    if w == node:
                        break

                # 只返回真正的循环（大小>1）
                if len(scc) > 1:
                    sccs.append(scc)

        # 对所有未访问的节点执行算法
        for node in graph:
            if node not in index:
                strongconnect(node)

        return sccs

    async def traverse_dependencies(
        self,
        start_files: List[str],
        dependency_graph: Dict[str, List[str]],
        max_depth: int = 5,
        scope_pattern: str = None
    ) -> Set[str]:
        """
        BFS遍历依赖，使用visited集合防止循环

        Args:
            start_files: 起始文件（入口+关键文件）
            dependency_graph: 依赖图
            max_depth: 最大遍历深度（防止过度包含）
            scope_pattern: 限定范围（如 "app_cf/lib/cf_game/"），只包含此前缀的文件

        Returns:
            所有相关文件的集合
        """
        visited = set()
        queue = [(f, 0) for f in start_files]  # (file, depth)
        result = set(start_files)

        while queue:
            current_file, depth = queue.pop(0)

            # 超过深度限制或已访问，跳过
            if depth >= max_depth or current_file in visited:
                continue

            visited.add(current_file)

            # 获取当前文件的导入
            imports = dependency_graph.get(current_file, [])

            for imported_file in imports:
                # 范围过滤：只保留范围内的文件
                if scope_pattern and not imported_file.startswith(scope_pattern):
                    continue

                # 添加到结果集
                if imported_file not in result:
                    result.add(imported_file)
                    queue.append((imported_file, depth + 1))

        return result

    def topological_sort_files(
        self,
        files: List[str],
        dependency_graph: Dict[str, List[str]]
    ) -> List[str]:
        """
        对文件列表进行拓扑排序，使依赖在前，被依赖者在后

        Args:
            files: 需要排序的文件列表
            dependency_graph: 依赖图 {file: [imported_files]}

        Returns:
            按依赖顺序排列的文件列表（被依赖的文件在前）
        """
        # 只处理在files列表中的文件
        file_set = set(files)

        # 构建反向依赖图（计算入度）
        in_degree: Dict[str, int] = {f: 0 for f in files}
        reverse_graph: Dict[str, List[str]] = {f: [] for f in files}

        for file in files:
            # 只考虑在files列表中的依赖
            dependencies = [
                dep for dep in dependency_graph.get(file, [])
                if dep in file_set
            ]
            for dep in dependencies:
                in_degree[file] = in_degree.get(file, 0) + 1
                if dep not in reverse_graph:
                    reverse_graph[dep] = []
                reverse_graph[dep].append(file)

        # Kahn算法：找到所有入度为0的节点
        queue = [f for f in files if in_degree.get(f, 0) == 0]
        result = []
        processed = set()

        # 处理循环依赖：如果所有节点都有入度，说明存在循环
        # 在这种情况下，按字母顺序处理
        if not queue:
            # 所有文件都在循环中，按字母顺序返回
            return sorted(files)

        # 拓扑排序主循环
        while queue:
            # 按字母顺序处理，保证结果稳定
            queue.sort()
            current = queue.pop(0)

            if current in processed:
                continue

            result.append(current)
            processed.add(current)

            # 更新依赖当前节点的文件的入度
            for dependent in reverse_graph.get(current, []):
                if dependent in processed:
                    continue
                in_degree[dependent] = in_degree.get(dependent, 0) - 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # 处理剩余的循环依赖节点（如果存在）
        remaining = [f for f in files if f not in processed]
        if remaining:
            # 对循环依赖的文件按字母顺序添加到末尾
            result.extend(sorted(remaining))

        return result

    def filter_by_scope(
        self,
        files: Set[str],
        module_base_path: str
    ) -> Set[str]:
        """
        过滤文件，确保它们在模块的范围内

        Args:
            files: 文件集合
            module_base_path: 模块基础路径（如 "app_cf/lib/cf_game/"）

        Returns:
            过滤后的文件集合
        """
        return {f for f in files if f.startswith(module_base_path)}

    def match_config_files_by_path(
        self,
        sub_module_name: str,
        orphan_files: List[str],
        module_base_path: str
    ) -> List[str]:
        """
        根据路径关键词匹配配置和资源文件到子模块

        Args:
            sub_module_name: 子模块名称
            orphan_files: 未分配的文件列表
            module_base_path: 模块基础路径

        Returns:
            匹配到的配置文件列表
        """
        # 从子模块名称提取关键词（如 "地图推荐功能" -> "map", "recommend"）
        keywords = self._extract_keywords_from_name(sub_module_name)

        matched = []
        for file in orphan_files:
            # 检查文件是否在模块范围内
            if not file.startswith(module_base_path):
                continue

            # 检查文件路径是否包含关键词
            file_lower = file.lower()
            for keyword in keywords:
                if keyword in file_lower:
                    matched.append(file)
                    break

        return matched

    def _extract_keywords_from_name(self, name: str) -> List[str]:
        """
        从模块名称提取关键词

        Args:
            name: 模块名称（如 "用户管理功能"）

        Returns:
            关键词列表（如 ["user", "management"]）
        """
        # 中文转拼音关键词映射（简化版）
        chinese_to_english = {
            '用户': 'user',
            '订单': 'order',
            '商品': 'product',
            '支付': 'payment',
            '购物车': 'cart',
            '地址': 'address',
            '评价': 'review',
            '收藏': 'favorite',
            '搜索': 'search',
            '推荐': 'recommend',
            '统计': 'statistics',
            '数据': 'data',
        }

        keywords = []

        # 提取中文关键词
        for chinese, english in chinese_to_english.items():
            if chinese in name:
                keywords.append(english)

        # 提取英文关键词（使用下划线或驼峰分割）
        # 例如："map_recommend" -> ["map", "recommend"]
        words = re.findall(r'[a-z]+', name.lower())
        keywords.extend(words)

        return list(set(keywords))  # 去重


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 循环依赖解决策略
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def resolve_circular_conflicts(
    sub_modules: List[Dict[str, Any]],
    circular_groups: List[Set[str]],
    dependency_graph: Dict[str, List[str]]
) -> None:
    """
    解决循环依赖导致的文件归属冲突

    核心思想：
    1. 计算每个子模块对循环组的"紧密度得分"
    2. 将整个循环组归属到得分最高的子模块
    3. 其他子模块标记为 shared_dependencies

    Args:
        sub_modules: 子模块列表（会被原地修改）
        circular_groups: 循环依赖组列表
        dependency_graph: 依赖图
    """
    print(f"        🔧 解决循环依赖冲突...")

    for circular_group in circular_groups:
        involved_modules = []

        # 找出涉及该循环组的所有子模块
        for sub_module in sub_modules:
            preliminary_files = set(sub_module.get('preliminary_files', []))
            overlap = circular_group & preliminary_files

            if not overlap:
                continue  # 该子模块不涉及此循环组

            # 计算紧密度得分（多因素）
            score = calculate_cohesion_score(
                sub_module=sub_module,
                circular_group=circular_group,
                overlap=overlap,
                dependency_graph=dependency_graph
            )

            involved_modules.append({
                'module': sub_module,
                'score': score,
                'overlap': overlap
            })

        # 如果只有一个或零个模块涉及，无冲突
        if len(involved_modules) <= 1:
            continue

        # 按得分排序，最高分的模块获得归属权
        involved_modules.sort(key=lambda x: x['score'], reverse=True)
        winner = involved_modules[0]

        print(f"           循环组 ({len(circular_group)} 个文件) -> {winner['module']['name']}")

        # 从其他模块移除该循环组
        for item in involved_modules[1:]:
            module = item['module']
            module['preliminary_files'] = [
                f for f in module['preliminary_files']
                if f not in circular_group
            ]

            # 标记为共享依赖
            if 'shared_dependencies' not in module:
                module['shared_dependencies'] = []
            module['shared_dependencies'].extend(list(item['overlap']))


def calculate_cohesion_score(
    sub_module: Dict[str, Any],
    circular_group: Set[str],
    overlap: Set[str],
    dependency_graph: Dict[str, List[str]]
) -> float:
    """
    计算子模块对循环组的紧密度得分

    评分因素：
    1. 入口文件数量（权重3）：循环组中有多少个是入口文件
    2. 关键文件数量（权重2）：循环组中有多少个是关键文件
    3. 路径距离（权重1）：循环组文件与子模块路径的平均距离
    4. 依赖密度（权重1）：循环组内部依赖vs外部依赖的比例

    Args:
        sub_module: 子模块信息
        circular_group: 循环依赖组
        overlap: 子模块与循环组的交集
        dependency_graph: 依赖图

    Returns:
        紧密度得分（归一化）
    """
    score = 0.0

    # 因素1：入口文件（最高优先级）
    entry_files = set(sub_module.get('suggested_entry_files', []))
    entry_count = len(overlap & entry_files)
    score += entry_count * 3.0

    # 因素2：关键文件
    key_files = set(sub_module.get('suggested_key_files', []))
    key_count = len(overlap & key_files)
    score += key_count * 2.0

    # 因素3：路径距离（越近越好）
    module_name = sub_module.get('name', '')
    path_distances = []

    for file in overlap:
        distance = calculate_path_distance(file, module_name)
        path_distances.append(distance)

    if path_distances:
        avg_distance = sum(path_distances) / len(path_distances)
        # 距离越近分数越高（10 - distance）
        score += max(0, 10 - min(avg_distance, 10)) * 1.0

    # 因素4：依赖密度
    internal_deps = count_internal_dependencies(
        circular_group, overlap, dependency_graph
    )
    external_deps = count_external_dependencies(
        circular_group, overlap, dependency_graph
    )

    if internal_deps + external_deps > 0:
        density = internal_deps / (internal_deps + external_deps)
        score += density * 1.0

    # 归一化（防止循环组大小影响）
    normalized_score = score / len(circular_group) if len(circular_group) > 0 else 0

    return normalized_score


def calculate_path_distance(file_path: str, module_name: str) -> int:
    """
    计算文件路径与模块名称的"距离"

    简化策略：统计文件路径中不包含模块名称关键词的层级数

    Args:
        file_path: 文件路径
        module_name: 模块名称

    Returns:
        距离值（0表示完全匹配）
    """
    # 提取模块名称中的关键词（转小写）
    module_keywords = re.findall(r'[a-z]+', module_name.lower())

    # 文件路径转小写
    file_lower = file_path.lower()

    # 如果文件路径包含任意关键词，距离为0
    for keyword in module_keywords:
        if keyword in file_lower:
            return 0

    # 否则，距离为路径层级数
    return file_path.count('/')


def count_internal_dependencies(
    circular_group: Set[str],
    overlap: Set[str],
    dependency_graph: Dict[str, List[str]]
) -> int:
    """
    统计循环组内部的依赖数量

    Args:
        circular_group: 循环依赖组
        overlap: 子模块与循环组的交集
        dependency_graph: 依赖图

    Returns:
        内部依赖数量
    """
    count = 0
    for file in overlap:
        imports = dependency_graph.get(file, [])
        for imp in imports:
            if imp in circular_group:
                count += 1
    return count


def count_external_dependencies(
    circular_group: Set[str],
    overlap: Set[str],
    dependency_graph: Dict[str, List[str]]
) -> int:
    """
    统计循环组外部的依赖数量

    Args:
        circular_group: 循环依赖组
        overlap: 子模块与循环组的交集
        dependency_graph: 依赖图

    Returns:
        外部依赖数量
    """
    count = 0
    for file in overlap:
        imports = dependency_graph.get(file, [])
        for imp in imports:
            if imp not in circular_group:
                count += 1
    return count

