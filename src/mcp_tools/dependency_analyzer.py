"""
依赖分析器 - 构建和分析模块依赖关系图

功能:
1. 基于导入关系构建有向图
2. 检测循环依赖
3. 计算模块耦合度
4. 识别核心模块和工具模块
5. 导出 Mermaid 依赖图
"""

from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
import logging

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logging.warning("networkx not installed, dependency analysis disabled")

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """模块依赖关系分析器"""

    def __init__(self):
        """初始化分析器"""
        if not HAS_NETWORKX:
            raise RuntimeError(
                "networkx not installed. Install with: pip install networkx"
            )

        self.graph = nx.DiGraph()
        self.module_info: Dict[str, Dict] = {}

    def add_module(
        self,
        module_path: str,
        imports: List[str],
        exports: List[str],
        language: str
    ):
        """
        添加模块到依赖图

        Args:
            module_path: 模块路径
            imports: 导入的模块列表
            exports: 导出的项列表
            language: 编程语言
        """
        # 添加节点
        self.graph.add_node(module_path)

        # 保存模块信息
        self.module_info[module_path] = {
            'imports': imports,
            'exports': exports,
            'language': language
        }

        # 添加边 (依赖关系)
        for imported_module in imports:
            # 尝试解析导入路径
            resolved_path = self._resolve_import(module_path, imported_module)
            if resolved_path and resolved_path in self.graph.nodes:
                self.graph.add_edge(module_path, resolved_path)
            else:
                # 外部依赖,也添加到图中
                self.graph.add_node(imported_module, external=True)
                self.graph.add_edge(module_path, imported_module)

    def _resolve_import(self, current_module: str, import_path: str) -> Optional[str]:
        """
        解析导入路径到实际文件路径

        Args:
            current_module: 当前模块路径
            import_path: 导入路径

        Returns:
            解析后的文件路径,失败返回 None
        """
        current_dir = Path(current_module).parent

        # 处理相对导入
        if import_path.startswith('.'):
            # Python 相对导入
            try:
                resolved = (current_dir / import_path.replace('.', '/')).resolve()
                return str(resolved)
            except Exception:
                return None

        # 处理绝对路径导入 (简化处理)
        # 实际项目中需要考虑更多情况
        return import_path

    def analyze_dependencies(self) -> Dict:
        """
        分析依赖关系

        Returns:
            分析结果字典:
            {
                "total_modules": int,
                "internal_modules": int,
                "external_modules": int,
                "cyclic_dependencies": List[List[str]],
                "strongly_connected_components": List[List[str]],
                "module_layers": Dict[str, List[str]],
                "coupling_scores": Dict[str, float],
                "hub_modules": List[str]
            }
        """
        if not self.graph.nodes:
            logger.warning("No modules in dependency graph")
            return {}

        result = {
            "total_modules": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
        }

        # 分离内部和外部模块
        internal_nodes = [
            n for n in self.graph.nodes
            if not self.graph.nodes[n].get('external', False)
        ]
        external_nodes = [
            n for n in self.graph.nodes
            if self.graph.nodes[n].get('external', False)
        ]

        result["internal_modules"] = len(internal_nodes)
        result["external_modules"] = len(external_nodes)

        # 检测循环依赖
        cycles = list(nx.simple_cycles(self.graph))
        result["cyclic_dependencies"] = cycles
        result["has_cycles"] = len(cycles) > 0

        # 强连通分量
        sccs = list(nx.strongly_connected_components(self.graph))
        result["strongly_connected_components"] = [list(scc) for scc in sccs]

        # 计算耦合度
        result["coupling_scores"] = self._calculate_coupling_scores()

        # 识别核心模块 (高出度和入度)
        result["hub_modules"] = self._identify_hub_modules()

        # 模块分层
        result["module_layers"] = self._analyze_module_layers()

        return result

    def _calculate_coupling_scores(self) -> Dict[str, float]:
        """
        计算每个模块的耦合度分数

        耦合度 = (出度 + 入度) / 总模块数
        """
        scores = {}
        total_nodes = self.graph.number_of_nodes()

        if total_nodes == 0:
            return scores

        for node in self.graph.nodes:
            if self.graph.nodes[node].get('external', False):
                continue

            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)

            # 归一化分数
            score = (in_degree + out_degree) / (2 * total_nodes)
            scores[node] = score

        return scores

    def _identify_hub_modules(self, threshold: float = 0.1) -> List[str]:
        """
        识别核心模块 (hub)

        核心模块定义: 耦合度分数超过阈值
        """
        coupling_scores = self._calculate_coupling_scores()

        hubs = [
            module for module, score in coupling_scores.items()
            if score > threshold
        ]

        # 按分数排序
        hubs.sort(key=lambda m: coupling_scores[m], reverse=True)

        return hubs

    def _analyze_module_layers(self) -> Dict[str, List[str]]:
        """
        分析模块层次结构

        Returns:
            {
                "layer_0": ["底层模块"],  # 无依赖
                "layer_1": ["中层模块"],
                "layer_2": ["高层模块"],
                ...
            }
        """
        layers: Dict[int, List[str]] = defaultdict(list)

        # 使用拓扑排序确定层次
        try:
            # 获取内部节点的子图
            internal_nodes = [
                n for n in self.graph.nodes
                if not self.graph.nodes[n].get('external', False)
            ]
            subgraph = self.graph.subgraph(internal_nodes)

            # 计算每个节点的最长路径长度作为层次
            for node in subgraph.nodes:
                # 计算从无依赖节点到当前节点的最长路径
                if subgraph.in_degree(node) == 0:
                    layers[0].append(node)
                else:
                    max_layer = 0
                    for predecessor in subgraph.predecessors(node):
                        for layer_num, layer_nodes in layers.items():
                            if predecessor in layer_nodes:
                                max_layer = max(max_layer, layer_num + 1)
                    layers[max_layer].append(node)

        except Exception as e:
            logger.warning(f"Error analyzing module layers: {e}")

        # 转换为字符串键
        return {f"layer_{k}": v for k, v in layers.items()}

    def generate_mermaid_graph(self, max_nodes: int = 50) -> str:
        """
        生成 Mermaid 格式的依赖图

        Args:
            max_nodes: 最大显示节点数 (避免图太大)

        Returns:
            Mermaid 图代码
        """
        if not self.graph.nodes:
            return "graph LR\n    A[No modules]"

        mermaid = ["graph LR"]

        # 只显示内部模块和最重要的外部依赖
        internal_nodes = [
            n for n in self.graph.nodes
            if not self.graph.nodes[n].get('external', False)
        ]

        # 限制节点数量
        if len(internal_nodes) > max_nodes:
            # 选择最重要的节点 (根据度数)
            node_degrees = [
                (n, self.graph.in_degree(n) + self.graph.out_degree(n))
                for n in internal_nodes
            ]
            node_degrees.sort(key=lambda x: x[1], reverse=True)
            internal_nodes = [n for n, _ in node_degrees[:max_nodes]]

        # 生成节点标签
        node_ids = {}
        for i, node in enumerate(internal_nodes):
            node_id = f"N{i}"
            node_ids[node] = node_id

            # 简化节点名称 (只显示文件名)
            label = Path(node).name

            mermaid.append(f"    {node_id}[\"{label}\"]")

        # 生成边
        for source in internal_nodes:
            for target in self.graph.successors(source):
                if target in node_ids:
                    source_id = node_ids[source]
                    target_id = node_ids[target]
                    mermaid.append(f"    {source_id} --> {target_id}")

        return "\n".join(mermaid)

    def export_to_dict(self) -> Dict:
        """
        导出依赖图为字典格式

        Returns:
            {
                "nodes": [...],
                "edges": [...],
                "analysis": {...}
            }
        """
        nodes = []
        for node in self.graph.nodes:
            node_data = {
                "id": node,
                "external": self.graph.nodes[node].get('external', False),
                "in_degree": self.graph.in_degree(node),
                "out_degree": self.graph.out_degree(node),
            }
            if node in self.module_info:
                node_data.update(self.module_info[node])
            nodes.append(node_data)

        edges = [
            {"source": u, "target": v}
            for u, v in self.graph.edges
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "analysis": self.analyze_dependencies()
        }


def create_dependency_analyzer() -> DependencyAnalyzer:
    """创建依赖分析器实例"""
    return DependencyAnalyzer()
