"""
Dart Analyzer - 基于 Dart 官方工具的代码分析

通过调用 dart analyze 命令来分析 Dart 代码，提取导入导出信息
"""

import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DartAnalyzer:
    """Dart 代码分析器"""

    # 需要排除的第三方包（黑名单）
    EXCLUDED_PACKAGES = {
        'flutter', 'flutter_test', 'flutter_driver', 'flutter_web_plugins',
        'flagen',
        'provider', 'riverpod', 'bloc', 'get', 'getx',
        'dio', 'http', 'retrofit',
        'sqflite', 'hive', 'shared_preferences',
        'firebase_core', 'firebase_auth', 'firebase_messaging',
        'google_maps_flutter', 'webview_flutter',
        'camera', 'image_picker', 'path_provider',
        'permission_handler', 'geolocator', 'url_launcher',
        'intl', 'json_annotation', 'freezed_annotation',
        'equatable', 'dartz', 'rxdart',
    }

    @staticmethod
    def is_dart_available() -> bool:
        """检查 dart 命令是否可用"""
        try:
            result = subprocess.run(
                ['dart', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def extract_imports_from_source(source_code: str) -> List[Dict[str, Any]]:
        """
        从 Dart 源码中提取 import 语句（使用正则表达式）

        Args:
            source_code: Dart 源代码

        Returns:
            导入信息列表
        """
        imports = []

        # 匹配 import 语句的正则表达式
        # import 'package:xxx/xxx.dart';
        # import 'xxx.dart';
        # import 'package:xxx/xxx.dart' as xxx;
        # import 'package:xxx/xxx.dart' show xxx, yyy;
        # import 'package:xxx/xxx.dart' hide xxx;
        import_pattern = re.compile(
            r"import\s+['\"]([^'\"]+)['\"]\s*(?:as\s+(\w+))?\s*(?:(show|hide)\s+([^;]+))?\s*;",
            re.MULTILINE
        )

        for match in import_pattern.finditer(source_code):
            source = match.group(1)
            alias = match.group(2)
            show_hide = match.group(3)
            items_str = match.group(4)

            import_info = {
                'source': source,
                'type': 'import'
            }

            if alias:
                import_info['alias'] = alias

            if show_hide and items_str:
                items = [item.strip() for item in items_str.split(',')]
                if show_hide == 'show':
                    import_info['show'] = items
                else:
                    import_info['hide'] = items

            imports.append(import_info)

        # 也处理 export 语句
        export_pattern = re.compile(
            r"export\s+['\"]([^'\"]+)['\"]\s*(?:(show|hide)\s+([^;]+))?\s*;",
            re.MULTILINE
        )

        for match in export_pattern.finditer(source_code):
            source = match.group(1)
            show_hide = match.group(2)
            items_str = match.group(3)

            export_info = {
                'source': source,
                'type': 'export'
            }

            if show_hide and items_str:
                items = [item.strip() for item in items_str.split(',')]
                if show_hide == 'show':
                    export_info['show'] = items
                else:
                    export_info['hide'] = items

            imports.append(export_info)

        return imports

    @staticmethod
    def is_project_import(source: str) -> bool:
        """
        判断是否是项目内部导入（非系统库、非第三方包、非自动生成文件）

        Args:
            source: import/export 的 source 路径

        Returns:
            True 如果是项目内部文件，False 如果是系统库或第三方包
        """
        # 排除 dart: 标准库
        if source.startswith('dart:'):
            return False

        # 排除自动生成的资源文件 r.dart
        if source.endswith('/r.dart') or source == 'r.dart':
            return False

        # 处理 package: 导入
        if source.startswith('package:'):
            # 提取包名 (package:xxx/path => xxx)
            package_name = source.replace('package:', '').split('/')[0]

            # 如果在黑名单中，则排除
            if package_name in DartAnalyzer.EXCLUDED_PACKAGES:
                return False

            # 其他 package: 开头的导入视为项目内部包
            return True

        # 相对路径导入（../, ./, 或直接文件名）是项目内部文件
        return True

    @staticmethod
    def extract_structure(file_path: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
        """
        提取 Dart 文件的结构信息

        Args:
            file_path: Dart 文件路径
            repo_root: 仓库根路径（可选）

        Returns:
            包含 imports, exports, classes, functions 的字典
        """
        file_path = Path(file_path)

        # 如果文件名是sale_item_detail_share_widget.dart， 则打印一条日志
        if file_path.name == 'sale_item_detail_share_widget.dart':
            logger.info(f"Extracting imports from {file_path}")

        if not file_path.exists():
            return {
                'success': False,
                'error': f'File not found: {file_path}'
            }

        try:
            # 读取源代码
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # 提取 imports/exports
            imports = DartAnalyzer.extract_imports_from_source(source_code)

            # 分离 imports 和 exports，并过滤掉系统库和第三方包
            import_list = [
                imp for imp in imports
                if imp.get('type') == 'import' and DartAnalyzer.is_project_import(imp.get('source', ''))
            ]
            export_list = [
                exp for exp in imports
                if exp.get('type') == 'export' and DartAnalyzer.is_project_import(exp.get('source', ''))
            ]

            return {
                'success': True,
                'file_path': str(file_path),
                'language': 'dart',
                'imports': import_list,
                'exports': export_list
            }

        except Exception as e:
            logger.error(f"Error analyzing Dart file {file_path}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }


def extract_dart_imports(file_path: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    """
    提取 Dart 文件的导入导出信息（便捷函数）

    Args:
        file_path: Dart 文件路径
        repo_root: 仓库根路径

    Returns:
        导入导出信息
    """
    analyzer = DartAnalyzer()
    return analyzer.extract_structure(file_path, repo_root)

