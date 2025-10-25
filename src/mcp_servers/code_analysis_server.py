"""
MCP 代码分析工具集

提供给 Claude Agent SDK 使用的 MCP (Model Context Protocol) 工具集。

工具列表:
1. scan_repository_structure - 扫描代码仓库结构
2. extract_imports_and_exports - 提取文件的导入导出关系
3. analyze_code_block - 深度分析代码片段
4. build_dependency_graph - 构建模块依赖关系图
5. search_code_patterns - 搜索特定代码模式
6. validate_analysis_result - 验证分析结果准确性
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import logging

# Claude Agent SDK
from claude_agent_sdk import tool, create_sdk_mcp_server

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_tools.language_detector import get_language_detector
from mcp_tools.file_filter import FileFilter
from mcp_tools.polyglot_parser import get_polyglot_parser
from mcp_tools.universal_extractor import create_extractor
from mcp_tools.dependency_analyzer import create_dependency_analyzer

logger = logging.getLogger(__name__)


# ============================================================================
# MCP 工具定义
# ============================================================================

def scan_repository_structure(
    repo_path: str,
    max_depth: int = 5,
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    扫描代码仓库结构,返回目录树和文件统计

    Args:
        repo_path: 仓库根目录路径
        max_depth: 最大扫描深度 (默认 5)
        include_extensions: 只包含的文件扩展名列表 (如 ['.py', '.js'])
        exclude_patterns: 额外排除的文件模式列表

    Returns:
        {
            "success": bool,
            "tree": "目录树字符串",
            "stats": {
                "total_files": int,
                "by_language": {"python": 10, "javascript": 5, ...},
                "by_category": {"source": 15, "config": 3, ...}
            },
            "files": [{"path": str, "language": str, "size": int}, ...],
            "error": str (如果失败)
        }
    """
    try:
        repo_path = Path(repo_path)

        if not repo_path.exists():
            return {
                "success": False,
                "error": f"Repository path does not exist: {repo_path}"
            }

        # 创建文件过滤器
        file_filter = FileFilter(
            exclude_patterns=set(exclude_patterns) if exclude_patterns else None
        )

        # 扫描文件
        ext_set = set(include_extensions) if include_extensions else None
        files = list(file_filter.scan_directory(
            repo_path,
            max_depth=max_depth,
            include_extensions=ext_set
        ))

        # 语言检测
        detector = get_language_detector()
        file_infos = []
        language_counts = {}
        category_counts = {}

        for file_path in files:
            language = detector.detect_language(file_path)
            category = detector.get_language_category(language) if language else "unknown"

            file_infos.append({
                "path": str(file_path.relative_to(repo_path)),
                "language": language or "unknown",
                "category": category,
                "size": file_path.stat().st_size
            })

            # 统计
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1

        # 生成目录树 (简化版)
        tree = _generate_tree_view(files, repo_path)

        return {
            "success": True,
            "tree": tree,
            "stats": {
                "total_files": len(files),
                "by_language": language_counts,
                "by_category": category_counts,
                "total_size_bytes": sum(f["size"] for f in file_infos)
            },
            "files": file_infos
        }

    except Exception as e:
        logger.error(f"Error scanning repository: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def extract_imports_and_exports(
    file_path: str,
    language: Optional[str] = None,
    repo_root: Optional[str] = None
) -> Dict[str, Any]:
    """
    提取文件的导入导出关系

    Args:
        file_path: 文件路径（可以是相对路径或绝对路径）
        language: 编程语言 (可选,自动检测)
        repo_root: 仓库根目录（可选，用于解析相对路径）

    Returns:
        {
            "success": bool,
            "file_path": str,
            "language": str,
            "imports": [{"module": str, "items": [...], "alias": str}, ...],
            "exports": [str, ...],
            "functions": [{"name": str, "params": [...], "start_line": int}, ...],
            "classes": [{"name": str, "methods": [...], "start_line": int}, ...],
            "error": str (如果失败)
        }
    """
    try:
        file_path = Path(file_path)

        # 如果是相对路径且提供了 repo_root，则转换为绝对路径
        if not file_path.is_absolute() and repo_root:
            file_path = Path(repo_root) / file_path

        if not file_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: {file_path}"
            }

        # 检测语言
        if not language:
            detector = get_language_detector()
            language = detector.detect_language(file_path)

        if not language:
            return {
                "success": False,
                "error": "Unable to detect language"
            }

        # 解析文件
        parser = get_polyglot_parser()

        if not parser.is_language_supported(language):
            return {
                "success": False,
                "error": f"Language '{language}' is not supported for parsing"
            }

        # 提取结构
        extractor = create_extractor(parser)
        structure = extractor.extract_structure(str(file_path), language)

        if not structure:
            return {
                "success": False,
                "error": "Failed to extract structure"
            }

        # 转换为字典
        result = structure.to_dict()
        result.update({
            "success": True,
            "file_path": str(file_path)
        })

        return result

    except Exception as e:
        logger.error(f"Error extracting imports/exports: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def analyze_code_block(
    code: str,
    language: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    深度分析代码片段的功能逻辑

    注意: 此工具主要用于提供结构化的代码信息,供 Claude 进行语义分析。
    实际的语义理解由 Claude 完成。

    Args:
        code: 代码片段
        language: 编程语言
        context: 上下文信息 (项目名称、整体功能等)

    Returns:
        {
            "success": bool,
            "language": str,
            "structure": {
                "functions": [...],
                "classes": [...],
                "imports": [...]
            },
            "context": {...},
            "suggestions": [
                "This code should be analyzed by Claude for semantic understanding"
            ],
            "error": str (如果失败)
        }
    """
    try:
        # 解析代码
        parser = get_polyglot_parser()

        if not parser.is_language_supported(language):
            return {
                "success": False,
                "error": f"Language '{language}' is not supported"
            }

        # 解析代码字符串
        parse_result = parser.parse_code(code, language)

        if not parse_result or not parse_result['success']:
            return {
                "success": False,
                "error": "Failed to parse code"
            }

        # 提取结构信息
        extractor = create_extractor(parser)
        tree = parse_result['tree']
        source = parse_result['source']

        # 提取各种结构 (简化处理)
        functions = extractor._extract_functions(tree, source, language)
        classes = extractor._extract_classes(tree, source, language)
        imports = extractor._extract_imports(tree, source, language)

        return {
            "success": True,
            "language": language,
            "structure": {
                "functions": [
                    {
                        "name": f.name,
                        "params": f.params,
                        "start_line": f.start_line,
                        "end_line": f.end_line
                    }
                    for f in functions
                ],
                "classes": [
                    {
                        "name": c.name,
                        "methods": c.methods,
                        "start_line": c.start_line,
                        "end_line": c.end_line
                    }
                    for c in classes
                ],
                "imports": [
                    {
                        "module": i.module,
                        "items": i.items,
                        "alias": i.alias
                    }
                    for i in imports
                ]
            },
            "context": context or {},
            "suggestions": [
                "Use Claude to analyze the business logic and purpose of this code",
                "Extract function descriptions based on code behavior",
                "Identify patterns and architectural decisions"
            ]
        }

    except Exception as e:
        logger.error(f"Error analyzing code block: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def build_dependency_graph(
    module_imports: List[Dict[str, Any]],
    output_format: str = "json"
) -> Dict[str, Any]:
    """
    构建模块依赖关系图

    Args:
        module_imports: 所有模块的导入信息列表
            [
                {
                    "module_path": str,
                    "imports": [str, ...],
                    "exports": [str, ...],
                    "language": str
                },
                ...
            ]
        output_format: 输出格式 ('json' 或 'mermaid')

    Returns:
        {
            "success": bool,
            "graph": {
                "nodes": [...],
                "edges": [...],
                "analysis": {
                    "total_modules": int,
                    "has_cycles": bool,
                    "cyclic_dependencies": [...],
                    "hub_modules": [...]
                }
            },
            "mermaid": str (如果 output_format='mermaid'),
            "error": str (如果失败)
        }
    """
    try:
        # 创建依赖分析器
        analyzer = create_dependency_analyzer()

        # 添加所有模块
        for module_info in module_imports:
            analyzer.add_module(
                module_path=module_info["module_path"],
                imports=module_info.get("imports", []),
                exports=module_info.get("exports", []),
                language=module_info.get("language", "unknown")
            )

        # 分析依赖
        graph_dict = analyzer.export_to_dict()

        result = {
            "success": True,
            "graph": graph_dict
        }

        # 生成 Mermaid 图
        if output_format == "mermaid":
            result["mermaid"] = analyzer.generate_mermaid_graph()

        return result

    except Exception as e:
        logger.error(f"Error building dependency graph: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def search_code_patterns(
    repo_path: str,
    pattern_type: str,
    language: Optional[str] = None
) -> Dict[str, Any]:
    """
    搜索特定代码模式

    Args:
        repo_path: 仓库路径
        pattern_type: 模式类型
            - 'api_routes': API 路由定义
            - 'db_models': 数据库模型
            - 'config': 配置项
            - 'test_cases': 测试用例
        language: 限制语言 (可选)

    Returns:
        {
            "success": bool,
            "pattern_type": str,
            "matches": [
                {
                    "file": str,
                    "line": int,
                    "code": str,
                    "context": {...}
                },
                ...
            ],
            "error": str (如果失败)
        }
    """
    try:
        # TODO: 实现模式搜索逻辑
        # 这里提供框架,具体实现需要根据不同语言定制

        return {
            "success": True,
            "pattern_type": pattern_type,
            "matches": [],
            "note": "Pattern search is not fully implemented yet"
        }

    except Exception as e:
        logger.error(f"Error searching patterns: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def validate_analysis_result(
    analysis: Dict[str, Any],
    source_code: str,
    language: str
) -> Dict[str, Any]:
    """
    验证分析结果是否准确 (防止 AI 编造)

    Args:
        analysis: AI 生成的分析结果
        source_code: 原始源代码
        language: 编程语言

    Returns:
        {
            "success": bool,
            "is_valid": bool,
            "confidence_score": float (0.0-1.0),
            "errors": [str, ...],
            "warnings": [str, ...],
            "error": str (如果失败)
        }
    """
    try:
        errors = []
        warnings = []

        # 解析源代码
        parser = get_polyglot_parser()
        parse_result = parser.parse_code(source_code, language)

        if not parse_result or not parse_result['success']:
            return {
                "success": False,
                "error": "Failed to parse source code for validation"
            }

        # 提取实际结构
        extractor = create_extractor(parser)
        tree = parse_result['tree']
        source = parse_result['source']

        actual_functions = extractor._extract_functions(tree, source, language)
        actual_classes = extractor._extract_classes(tree, source, language)

        # 验证函数
        if "functions" in analysis:
            claimed_functions = set(
                f.get("name") for f in analysis["functions"]
            )
            actual_function_names = set(f.name for f in actual_functions)

            # 检查是否有编造的函数
            fake_functions = claimed_functions - actual_function_names
            if fake_functions:
                errors.append(
                    f"Claimed functions not found in code: {list(fake_functions)}"
                )

            # 检查是否有遗漏的函数
            missing_functions = actual_function_names - claimed_functions
            if missing_functions:
                warnings.append(
                    f"Functions found but not mentioned: {list(missing_functions)}"
                )

        # 验证类
        if "classes" in analysis:
            claimed_classes = set(
                c.get("name") for c in analysis["classes"]
            )
            actual_class_names = set(c.name for c in actual_classes)

            fake_classes = claimed_classes - actual_class_names
            if fake_classes:
                errors.append(
                    f"Claimed classes not found in code: {list(fake_classes)}"
                )

        # 计算置信度分数
        total_checks = len(actual_functions) + len(actual_classes)
        if total_checks == 0:
            confidence_score = 1.0
        else:
            error_count = len(errors)
            confidence_score = max(0.0, 1.0 - (error_count / total_checks))

        return {
            "success": True,
            "is_valid": len(errors) == 0,
            "confidence_score": confidence_score,
            "errors": errors,
            "warnings": warnings
        }

    except Exception as e:
        logger.error(f"Error validating analysis: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# 辅助函数
# ============================================================================

def _generate_tree_view(files: List[Path], root: Path) -> str:
    """生成目录树视图 (简化版)"""
    tree_lines = []

    # 按路径排序
    sorted_files = sorted(files, key=lambda f: str(f.relative_to(root)))

    # 生成树
    for file_path in sorted_files[:50]:  # 限制显示数量
        rel_path = file_path.relative_to(root)
        indent = "  " * (len(rel_path.parts) - 1)
        tree_lines.append(f"{indent}├── {file_path.name}")

    if len(files) > 50:
        tree_lines.append(f"... and {len(files) - 50} more files")

    return "\n".join(tree_lines)


# ============================================================================
# Claude Agent SDK 工具定义
# ============================================================================

# 创建异步包装函数以适配 @tool 装饰器的要求
# tool 装饰器期望：async def func(args: dict) -> dict

@tool(
    name="scan_repository_structure",
    description="扫描代码仓库结构,返回目录树、文件统计和语言分布信息",
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "仓库根目录的绝对路径"
            },
            "max_depth": {
                "type": "integer",
                "description": "最大扫描深度,默认5层",
                "default": 5
            },
            "include_extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "只包含的文件扩展名列表,如['.py', '.js']"
            },
            "exclude_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "额外排除的文件模式"
            }
        },
        "required": ["repo_path"]
    }
)
async def scan_repo_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """异步包装器：调用同步的 scan_repository_structure 函数"""
    result = scan_repository_structure(
        repo_path=args["repo_path"],
        max_depth=args.get("max_depth", 5),
        include_extensions=args.get("include_extensions"),
        exclude_patterns=args.get("exclude_patterns")
    )

    # 转换为 MCP 格式
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }

@tool(
    name="extract_imports_and_exports",
    description="提取指定文件的导入导出关系、函数和类定义",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要分析的文件路径（相对路径或绝对路径）"
            },
            "language": {
                "type": "string",
                "description": "编程语言(可选,会自动检测)"
            },
            "repo_root": {
                "type": "string",
                "description": "仓库根目录路径（可选，用于解析相对路径。如果 file_path 是相对路径，必须提供此参数）"
            }
        },
        "required": ["file_path"]
    }
)
async def extract_imports_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """异步包装器：调用同步的 extract_imports_and_exports 函数"""
    result = extract_imports_and_exports(
        file_path=args["file_path"],
        language=args.get("language"),
        repo_root=args.get("repo_root")
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }

@tool(
    name="analyze_code_block",
    description="深度分析代码片段,提取结构化信息(函数、类、导入等)",
    input_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要分析的代码片段"
            },
            "language": {
                "type": "string",
                "description": "编程语言(如python、javascript)"
            },
            "context": {
                "type": "object",
                "description": "上下文信息(项目名称、整体功能等)"
            }
        },
        "required": ["code", "language"]
    }
)
async def analyze_code_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """异步包装器：调用同步的 analyze_code_block 函数"""
    result = analyze_code_block(
        code=args["code"],
        language=args["language"],
        context=args.get("context")
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }

@tool(
    name="build_dependency_graph",
    description="构建模块依赖关系图,分析循环依赖和核心模块",
    input_schema={
        "type": "object",
        "properties": {
            "module_imports": {
                "type": "array",
                "description": "所有模块的导入信息列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "module_path": {"type": "string"},
                        "imports": {"type": "array", "items": {"type": "string"}},
                        "exports": {"type": "array", "items": {"type": "string"}},
                        "language": {"type": "string"}
                    }
                }
            },
            "output_format": {
                "type": "string",
                "enum": ["json", "mermaid"],
                "description": "输出格式",
                "default": "json"
            }
        },
        "required": ["module_imports"]
    }
)
async def build_dependency_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """异步包装器：调用同步的 build_dependency_graph 函数"""
    result = build_dependency_graph(
        module_imports=args["module_imports"],
        output_format=args.get("output_format", "json")
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }

@tool(
    name="search_code_patterns",
    description="搜索特定代码模式(API路由、数据库模型等)",
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "仓库路径"
            },
            "pattern_type": {
                "type": "string",
                "description": "模式类型:api_routes/db_models/config/test_cases"
            },
            "language": {
                "type": "string",
                "description": "限制语言(可选)"
            }
        },
        "required": ["repo_path", "pattern_type"]
    }
)
async def search_patterns_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """异步包装器：调用同步的 search_code_patterns 函数"""
    result = search_code_patterns(
        repo_path=args["repo_path"],
        pattern_type=args["pattern_type"],
        language=args.get("language")
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }

@tool(
    name="validate_analysis_result",
    description="验证AI分析结果的准确性,防止编造",
    input_schema={
        "type": "object",
        "properties": {
            "analysis": {
                "type": "object",
                "description": "AI生成的分析结果"
            },
            "source_code": {
                "type": "string",
                "description": "原始源代码"
            },
            "language": {
                "type": "string",
                "description": "编程语言"
            }
        },
        "required": ["analysis", "source_code", "language"]
    }
)
async def validate_analysis_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """异步包装器：调用同步的 validate_analysis_result 函数"""
    result = validate_analysis_result(
        analysis=args["analysis"],
        source_code=args["source_code"],
        language=args["language"]
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }

# 创建 MCP Server
def create_code_analysis_mcp_server():
    """创建代码分析 MCP Server"""
    return create_sdk_mcp_server(
        name="code-analysis-tools",
        version="1.0.0",
        tools=[
            scan_repo_tool,
            extract_imports_tool,
            analyze_code_tool,
            build_dependency_tool,
            search_patterns_tool,
            validate_analysis_tool
        ]
    )


if __name__ == "__main__":
    # 测试工具
    import sys

    if len(sys.argv) < 2:
        print("Usage: python code_analysis_server.py <repo_path>")
        sys.exit(1)

    repo_path = sys.argv[1]

    print("Testing scan_repository_structure...")
    result = scan_repository_structure(repo_path, max_depth=3)
    print(json.dumps(result, indent=2, ensure_ascii=False))
