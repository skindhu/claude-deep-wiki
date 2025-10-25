"""
语言检测器 - 基于多重策略的编程语言自动识别

支持策略:
1. 文件扩展名映射
2. Shebang 行检测 (#!/usr/bin/python)
3. 文件内容特征匹配
"""

import re
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class LanguageDetector:
    """多策略编程语言检测器"""

    # 扩展名到语言的映射 (支持主流语言)
    EXTENSION_MAP: Dict[str, str] = {
        # Python
        '.py': 'python',
        '.pyw': 'python',
        '.pyi': 'python',

        # JavaScript/TypeScript
        '.js': 'javascript',
        '.mjs': 'javascript',
        '.cjs': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'tsx',
        '.mts': 'typescript',

        # Web
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',

        # Java/JVM
        '.java': 'java',
        '.kt': 'kotlin',
        '.kts': 'kotlin',
        '.scala': 'scala',
        '.groovy': 'groovy',

        # C/C++
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.cxx': 'cpp',
        '.cc': 'cpp',
        '.hpp': 'cpp',
        '.hxx': 'cpp',

        # C#
        '.cs': 'c_sharp',

        # Go
        '.go': 'go',

        # Rust
        '.rs': 'rust',

        # Ruby
        '.rb': 'ruby',
        '.rake': 'ruby',

        # PHP
        '.php': 'php',

        # Swift
        '.swift': 'swift',

        # Objective-C
        '.m': 'objc',
        '.mm': 'objc',

        # Shell
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'bash',

        # Lua
        '.lua': 'lua',

        # R
        '.r': 'r',
        '.R': 'r',

        # SQL
        '.sql': 'sql',

        # Config/Data
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.xml': 'xml',
        '.ini': 'ini',

        # Markdown/Docs
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.rst': 'rst',

        # Other
        '.dockerfile': 'dockerfile',
        '.makefile': 'makefile',
        '.cmake': 'cmake',
    }

    # Shebang 到语言的映射
    SHEBANG_MAP: Dict[str, str] = {
        'python': 'python',
        'python3': 'python',
        'python2': 'python',
        'node': 'javascript',
        'ruby': 'ruby',
        'perl': 'perl',
        'bash': 'bash',
        'sh': 'bash',
        'zsh': 'bash',
        'fish': 'fish',
    }

    def __init__(self):
        """初始化语言检测器"""
        # 编译 shebang 正则表达式
        self.shebang_pattern = re.compile(r'^#!\s*(?:/usr/bin/env\s+)?(\w+)')

    def detect_language(self, file_path: str | Path) -> Optional[str]:
        """
        检测文件的编程语言

        Args:
            file_path: 文件路径

        Returns:
            语言标识符 (如 'python', 'javascript'),失败返回 None
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        # 策略1: 文件扩展名
        language = self._detect_by_extension(file_path)
        if language:
            return language

        # 策略2: 文件名模式 (Dockerfile, Makefile 等)
        language = self._detect_by_filename(file_path)
        if language:
            return language

        # 策略3: Shebang 行
        try:
            language = self._detect_by_shebang(file_path)
            if language:
                return language
        except Exception as e:
            logger.debug(f"Failed to read shebang from {file_path}: {e}")

        return None

    def _detect_by_extension(self, file_path: Path) -> Optional[str]:
        """通过文件扩展名检测语言"""
        ext = file_path.suffix.lower()
        return self.EXTENSION_MAP.get(ext)

    def _detect_by_filename(self, file_path: Path) -> Optional[str]:
        """通过文件名检测语言"""
        filename_lower = file_path.name.lower()

        # 特殊文件名映射
        special_files = {
            'dockerfile': 'dockerfile',
            'makefile': 'makefile',
            'cmakelists.txt': 'cmake',
            'vagrantfile': 'ruby',
            'gemfile': 'ruby',
            'rakefile': 'ruby',
            'package.json': 'json',
            'tsconfig.json': 'json',
            '.eslintrc': 'json',
            '.prettierrc': 'json',
        }

        return special_files.get(filename_lower)

    def _detect_by_shebang(self, file_path: Path) -> Optional[str]:
        """通过 shebang 行检测语言"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()

            if first_line.startswith('#!'):
                match = self.shebang_pattern.match(first_line)
                if match:
                    interpreter = match.group(1)
                    return self.SHEBANG_MAP.get(interpreter)
        except Exception:
            pass

        return None

    def is_code_file(self, file_path: str | Path) -> bool:
        """
        判断文件是否是代码文件

        Args:
            file_path: 文件路径

        Returns:
            是否是代码文件
        """
        language = self.detect_language(file_path)

        # 排除纯配置/数据文件
        non_code_languages = {'json', 'yaml', 'toml', 'xml', 'ini', 'markdown', 'rst'}

        return language is not None and language not in non_code_languages

    def get_language_category(self, language: str) -> str:
        """
        获取语言类别

        Args:
            language: 语言标识符

        Returns:
            类别: source/config/docs/web
        """
        categories = {
            'source': {
                'python', 'javascript', 'typescript', 'tsx', 'java', 'kotlin',
                'scala', 'c', 'cpp', 'c_sharp', 'go', 'rust', 'ruby', 'php',
                'swift', 'objc', 'lua', 'r', 'sql'
            },
            'config': {'json', 'yaml', 'toml', 'xml', 'ini'},
            'docs': {'markdown', 'rst'},
            'web': {'html', 'css', 'scss', 'sass', 'less'},
            'build': {'dockerfile', 'makefile', 'cmake'},
        }

        for category, languages in categories.items():
            if language in languages:
                return category

        return 'other'


# 单例实例
_detector_instance: Optional[LanguageDetector] = None


def get_language_detector() -> LanguageDetector:
    """获取语言检测器单例"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = LanguageDetector()
    return _detector_instance
