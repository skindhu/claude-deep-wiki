"""
统一结构提取器 - 从不同语言的 AST 中提取标准化的代码结构

功能:
1. 提取函数定义 (跨语言统一格式)
2. 提取类定义
3. 提取导入语句
4. 提取导出语句
5. 提取函数调用关系
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    params: List[str]
    start_line: int
    end_line: int
    doc_comment: Optional[str] = None


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    methods: List[str]
    start_line: int
    end_line: int
    doc_comment: Optional[str] = None


@dataclass
class ImportInfo:
    """导入信息"""
    module: str
    items: List[str]  # 具体导入的项
    alias: Optional[str] = None


@dataclass
class CodeStructure:
    """统一的代码结构"""
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[ImportInfo]
    exports: List[str]
    language: str

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'functions': [asdict(f) for f in self.functions],
            'classes': [asdict(c) for c in self.classes],
            'imports': [asdict(i) for i in self.imports],
            'exports': self.exports,
            'language': self.language
        }


class UniversalExtractor:
    """跨语言代码结构提取器"""

    # 语言特定的 Tree-sitter 查询模式
    QUERY_PATTERNS = {
        'python': {
            'functions': '(function_definition name: (identifier) @func_name)',
            'classes': '(class_definition name: (identifier) @class_name)',
            'imports': '''
                (import_statement name: (dotted_name) @import)
                (import_from_statement module_name: (dotted_name) @import)
            ''',
        },
        'javascript': {
            'functions': '''
                (function_declaration name: (identifier) @func_name)
                (arrow_function) @arrow_func
                (method_definition name: (property_identifier) @method_name)
            ''',
            'classes': '(class_declaration name: (identifier) @class_name)',
            'imports': '(import_statement source: (string) @import)',
            'exports': '''
                (export_statement) @export
                (export_specifier) @export_item
            ''',
        },
        'typescript': {
            'functions': '''
                (function_declaration name: (identifier) @func_name)
                (method_definition name: (property_identifier) @method_name)
            ''',
            'classes': '(class_declaration name: (identifier) @class_name)',
            'imports': '(import_statement source: (string) @import)',
        },
        'java': {
            'functions': '(method_declaration name: (identifier) @method_name)',
            'classes': '(class_declaration name: (identifier) @class_name)',
            'imports': '(import_declaration (scoped_identifier) @import)',
        },
        'go': {
            'functions': '(function_declaration name: (identifier) @func_name)',
            'imports': '(import_spec path: (interpreted_string_literal) @import)',
        },
        'rust': {
            'functions': '(function_item name: (identifier) @func_name)',
            'imports': '(use_declaration argument: (scoped_identifier) @import)',
        },
        'dart': {
            'functions': '''
                (function_signature name: (identifier) @func_name)
                (method_signature name: (identifier) @method_name)
            ''',
            'classes': '''
                (class_definition name: (identifier) @class_name)
                (mixin_declaration name: (identifier) @mixin_name)
                (enum_declaration name: (identifier) @enum_name)
            ''',
            'imports': '''
                (import_or_export uri: (configurable_uri (string_literal) @import))
            ''',
            'exports': '''
                (import_or_export uri: (configurable_uri (string_literal) @export))
            ''',
        },
    }

    def __init__(self, parser):
        """
        初始化提取器

        Args:
            parser: PolyglotParser 实例
        """
        self.parser = parser

    def extract_structure(
        self,
        file_path: str,
        language: str
    ) -> Optional[CodeStructure]:
        """
        提取文件的代码结构

        Args:
            file_path: 文件路径
            language: 语言标识符

        Returns:
            CodeStructure 对象,失败返回 None
        """
        # 解析文件
        parse_result = self.parser.parse_file(file_path, language)

        if not parse_result or not parse_result['success']:
            logger.warning(f"Failed to parse {file_path}")
            return None

        tree = parse_result['tree']
        source = parse_result['source']

        # 提取各种结构
        functions = self._extract_functions(tree, source, language)
        classes = self._extract_classes(tree, source, language)
        imports = self._extract_imports(tree, source, language)
        exports = self._extract_exports(tree, source, language)

        return CodeStructure(
            functions=functions,
            classes=classes,
            imports=imports,
            exports=exports,
            language=language
        )

    def _extract_functions(
        self,
        tree,
        source: bytes,
        language: str
    ) -> List[FunctionInfo]:
        """提取函数定义"""
        functions = []

        # 获取查询模式
        query_pattern = self._get_query_pattern(language, 'functions')
        if not query_pattern:
            return functions

        try:
            captures = self.parser.query(tree, query_pattern, language)

            for node, capture_name in captures:
                func_name = self.parser.get_node_text(node, source)

                # 获取参数 (简化处理)
                params = self._extract_function_params(node, source, language)

                functions.append(FunctionInfo(
                    name=func_name,
                    params=params,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))

        except Exception as e:
            logger.debug(f"Error extracting functions for {language}: {e}")

        return functions

    def _extract_function_params(
        self,
        func_node,
        source: bytes,
        language: str
    ) -> List[str]:
        """提取函数参数列表"""
        params = []

        try:
            # 查找参数节点 (不同语言有不同的节点类型)
            param_types = {
                'python': 'parameters',
                'javascript': 'formal_parameters',
                'typescript': 'formal_parameters',
                'java': 'formal_parameters',
                'go': 'parameter_list',
            }

            param_type = param_types.get(language, 'parameters')

            for child in func_node.children:
                if child.type == param_type:
                    # 提取参数名
                    for param_child in child.children:
                        if param_child.type in ('identifier', 'parameter_declaration'):
                            param_text = self.parser.get_node_text(param_child, source)
                            if param_text and param_text not in ('(', ')', ','):
                                params.append(param_text)

        except Exception as e:
            logger.debug(f"Error extracting params: {e}")

        return params

    def _extract_classes(
        self,
        tree,
        source: bytes,
        language: str
    ) -> List[ClassInfo]:
        """提取类定义"""
        classes = []

        query_pattern = self._get_query_pattern(language, 'classes')
        if not query_pattern:
            return classes

        try:
            captures = self.parser.query(tree, query_pattern, language)

            for node, capture_name in captures:
                class_name = self.parser.get_node_text(node, source)

                # 提取类的方法 (简化处理)
                methods = self._extract_class_methods(node, source, language)

                classes.append(ClassInfo(
                    name=class_name,
                    methods=methods,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))

        except Exception as e:
            logger.debug(f"Error extracting classes for {language}: {e}")

        return classes

    def _extract_class_methods(
        self,
        class_node,
        source: bytes,
        language: str
    ) -> List[str]:
        """提取类的方法列表"""
        methods = []

        try:
            method_types = {
                'python': 'function_definition',
                'javascript': 'method_definition',
                'java': 'method_declaration',
            }

            method_type = method_types.get(language, 'method_definition')

            # 遍历类的子节点
            for child in class_node.children:
                if child.type == 'class_body' or child.type == 'declaration_list':
                    for method_node in child.children:
                        if method_node.type == method_type:
                            # 提取方法名
                            for name_node in method_node.children:
                                if name_node.type == 'identifier':
                                    method_name = self.parser.get_node_text(name_node, source)
                                    if method_name:
                                        methods.append(method_name)
                                    break

        except Exception as e:
            logger.debug(f"Error extracting methods: {e}")

        return methods

    def _extract_imports(
        self,
        tree,
        source: bytes,
        language: str
    ) -> List[ImportInfo]:
        """提取导入语句"""
        imports = []

        query_pattern = self._get_query_pattern(language, 'imports')
        if not query_pattern:
            return imports

        try:
            captures = self.parser.query(tree, query_pattern, language)

            for node, capture_name in captures:
                import_text = self.parser.get_node_text(node, source)

                # 清理导入文本 (去除引号等)
                import_text = import_text.strip().strip('"').strip("'")

                if import_text:
                    imports.append(ImportInfo(
                        module=import_text,
                        items=[],
                        alias=None
                    ))

        except Exception as e:
            logger.debug(f"Error extracting imports for {language}: {e}")

        return imports

    def _extract_exports(
        self,
        tree,
        source: bytes,
        language: str
    ) -> List[str]:
        """提取导出语句"""
        exports = []

        query_pattern = self._get_query_pattern(language, 'exports')
        if not query_pattern:
            return exports

        try:
            captures = self.parser.query(tree, query_pattern, language)

            for node, capture_name in captures:
                export_text = self.parser.get_node_text(node, source)
                if export_text:
                    exports.append(export_text)

        except Exception as e:
            logger.debug(f"Error extracting exports for {language}: {e}")

        return exports

    def _get_query_pattern(self, language: str, pattern_type: str) -> Optional[str]:
        """获取指定语言的查询模式"""
        lang_patterns = self.QUERY_PATTERNS.get(language, {})
        return lang_patterns.get(pattern_type)


def create_extractor(parser) -> UniversalExtractor:
    """创建提取器实例"""
    return UniversalExtractor(parser)
