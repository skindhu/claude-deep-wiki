"""
多语言解析器 - 基于 Tree-sitter 的统一代码解析接口

功能:
1. 支持 165+ 编程语言的 AST 解析
2. Parser 实例缓存提升性能
3. 统一的查询接口
4. 错误处理和降级方案
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

try:
    from tree_sitter_languages import get_language, get_parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    logging.warning("tree-sitter-languages not installed, parsing disabled")

logger = logging.getLogger(__name__)


class PolyglotParser:
    """语言无关的代码解析器"""

    # Tree-sitter 语言名称映射 (我们的命名 -> tree-sitter 命名)
    LANGUAGE_NAME_MAP = {
        'javascript': 'javascript',
        'typescript': 'typescript',
        'tsx': 'tsx',
        'python': 'python',
        'java': 'java',
        'go': 'go',
        'rust': 'rust',
        'cpp': 'cpp',
        'c': 'c',
        'c_sharp': 'c_sharp',
        'ruby': 'ruby',
        'php': 'php',
        'swift': 'swift',
        'kotlin': 'kotlin',
        'scala': 'scala',
        'html': 'html',
        'css': 'css',
        'json': 'json',
        'yaml': 'yaml',
        'bash': 'bash',
        'sql': 'sql',
        'r': 'r',
        'lua': 'lua',
        'objc': 'objc',
    }

    def __init__(self):
        """初始化解析器"""
        if not HAS_TREE_SITTER:
            raise RuntimeError(
                "tree-sitter-languages not installed. "
                "Install with: pip install tree-sitter-languages"
            )

        # Parser 缓存 {language: parser}
        self._parser_cache: Dict[str, Any] = {}

        # Language 缓存 {language: language_obj}
        self._language_cache: Dict[str, Any] = {}

    def get_parser(self, language: str):
        """
        获取指定语言的 parser (带缓存)

        Args:
            language: 语言标识符

        Returns:
            Tree-sitter parser 对象

        Raises:
            ValueError: 不支持的语言
        """
        # 映射语言名称
        ts_language = self.LANGUAGE_NAME_MAP.get(language, language)

        # 检查缓存
        if ts_language in self._parser_cache:
            return self._parser_cache[ts_language]

        try:
            parser = get_parser(ts_language)
            self._parser_cache[ts_language] = parser
            logger.debug(f"Loaded parser for {ts_language}")
            return parser
        except Exception as e:
            raise ValueError(f"Unsupported language: {language}") from e

    def get_language(self, language: str):
        """
        获取指定语言的 Language 对象 (带缓存)

        Args:
            language: 语言标识符

        Returns:
            Tree-sitter Language 对象
        """
        ts_language = self.LANGUAGE_NAME_MAP.get(language, language)

        if ts_language in self._language_cache:
            return self._language_cache[ts_language]

        try:
            lang_obj = get_language(ts_language)
            self._language_cache[ts_language] = lang_obj
            return lang_obj
        except Exception as e:
            raise ValueError(f"Unsupported language: {language}") from e

    def parse_file(self, file_path: str | Path, language: str) -> Optional[Dict[str, Any]]:
        """
        解析文件生成 AST

        Args:
            file_path: 文件路径
            language: 语言标识符

        Returns:
            解析结果字典:
            {
                "tree": AST根节点,
                "source": 源代码,
                "language": 语言,
                "success": 是否成功
            }
            失败返回 None
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            # 读取文件内容
            with open(file_path, 'rb') as f:
                source_code = f.read()

            # 解析
            return self.parse_code(source_code, language)

        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def parse_code(self, source_code: bytes | str, language: str) -> Optional[Dict[str, Any]]:
        """
        解析代码字符串生成 AST

        Args:
            source_code: 源代码 (bytes 或 str)
            language: 语言标识符

        Returns:
            解析结果字典,失败返回 None
        """
        # 确保是 bytes
        if isinstance(source_code, str):
            source_code = source_code.encode('utf-8')

        try:
            parser = self.get_parser(language)
            tree = parser.parse(source_code)

            return {
                "tree": tree,
                "root_node": tree.root_node,
                "source": source_code,
                "language": language,
                "success": True
            }

        except ValueError as e:
            logger.warning(f"Unsupported language {language}: {e}")
            return None
        except Exception as e:
            logger.error(f"Parse error for {language}: {e}")
            return None

    def query(self, tree, query_string: str, language: str) -> List[tuple]:
        """
        使用 Tree-sitter query 查询 AST

        Args:
            tree: 解析得到的 tree 对象
            query_string: S-expression 格式的查询字符串
            language: 语言标识符

        Returns:
            查询结果列表 [(node, capture_name), ...]

        Example:
            query_string = "(function_definition name: (identifier) @func_name)"
        """
        try:
            lang = self.get_language(language)

            # 创建查询
            query = lang.query(query_string)

            # 执行查询
            captures = query.captures(tree.root_node)

            return captures

        except Exception as e:
            logger.error(f"Query error: {e}")
            return []

    def get_node_text(self, node, source: bytes) -> str:
        """
        获取节点对应的源代码文本

        Args:
            node: AST 节点
            source: 源代码 bytes

        Returns:
            节点文本
        """
        try:
            return source[node.start_byte:node.end_byte].decode('utf-8')
        except Exception:
            return ""

    def is_language_supported(self, language: str) -> bool:
        """
        检查语言是否支持

        Args:
            language: 语言标识符

        Returns:
            是否支持
        """
        ts_language = self.LANGUAGE_NAME_MAP.get(language, language)

        try:
            self.get_parser(ts_language)
            return True
        except Exception:
            return False

    def get_supported_languages(self) -> List[str]:
        """
        获取所有支持的语言列表

        Returns:
            语言列表
        """
        return list(self.LANGUAGE_NAME_MAP.keys())


# 单例实例
_parser_instance: Optional[PolyglotParser] = None


def get_polyglot_parser() -> PolyglotParser:
    """获取解析器单例"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = PolyglotParser()
    return _parser_instance
