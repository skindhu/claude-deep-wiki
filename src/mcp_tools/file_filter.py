"""
文件过滤器 - 智能过滤代码仓库中的文件

功能:
1. 排除常见的无关目录 (.git, node_modules, __pycache__ 等)
2. 支持 .gitignore 规则解析
3. 文件类型分类
4. 可配置的过滤规则
"""

import os
import sys
from pathlib import Path
from typing import Set, List, Optional, Iterator
import logging

# 添加 src 到路径以便导入 config
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from config import DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_PATTERNS, MAX_FILE_SIZE_MB
except ImportError:
    # 如果配置文件不可用，使用默认值
    DEFAULT_EXCLUDE_DIRS = {
        '.git', '.svn', '.hg', '.bzr',
        'node_modules', 'vendor', 'bower_components',
        '__pycache__', '.pytest_cache', '.mypy_cache',
        'venv', '.venv', 'env', '.env', 'virtualenv',
        '*.egg-info', 'dist', 'build', '.tox',
        'target', 'out', 'output', 'bin', 'obj',
        '.idea', '.vscode', '.vs', '*.swp', '*.swo',
        '.DS_Store', 'Thumbs.db',
        '.cache', '.npm', '.yarn', '.gradle',
        'logs', '*.log',
        'tmp', 'temp', '.tmp',
    }
    DEFAULT_EXCLUDE_PATTERNS = {
        '*.pyc', '*.pyo', '*.pyd',
        '*.so', '*.dylib', '*.dll',
        '*.class', '*.jar',
        '*.o', '*.a',
        '*.min.js', '*.min.css',
        '*.map',
        '*.lock', 'package-lock.json', 'yarn.lock',
        '.DS_Store', 'Thumbs.db',
    }
    MAX_FILE_SIZE_MB = 10.0

try:
    import pathspec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False
    logging.warning("pathspec not installed, .gitignore support disabled")

logger = logging.getLogger(__name__)


class FileFilter:
    """智能文件过滤器"""

    # 从配置文件导入默认值
    DEFAULT_EXCLUDE_DIRS = DEFAULT_EXCLUDE_DIRS
    DEFAULT_EXCLUDE_PATTERNS = DEFAULT_EXCLUDE_PATTERNS

    def __init__(
        self,
        exclude_dirs: Optional[Set[str]] = None,
        exclude_patterns: Optional[Set[str]] = None,
        gitignore_path: Optional[str | Path] = None,
        max_file_size_mb: float = MAX_FILE_SIZE_MB
    ):
        """
        初始化文件过滤器

        Args:
            exclude_dirs: 要排除的目录集合 (None 使用默认值)
            exclude_patterns: 要排除的文件模式集合 (None 使用默认值)
            gitignore_path: .gitignore 文件路径 (None 则自动查找)
            max_file_size_mb: 最大文件大小限制 (MB)
        """
        self.exclude_dirs = exclude_dirs or self.DEFAULT_EXCLUDE_DIRS.copy()
        self.exclude_patterns = exclude_patterns or self.DEFAULT_EXCLUDE_PATTERNS.copy()
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)

        # 加载 .gitignore 规则
        self.gitignore_spec = None
        if HAS_PATHSPEC and gitignore_path:
            self._load_gitignore(gitignore_path)

    def _load_gitignore(self, gitignore_path: str | Path):
        """加载 .gitignore 文件"""
        gitignore_path = Path(gitignore_path)

        if not gitignore_path.exists():
            logger.debug(f".gitignore not found: {gitignore_path}")
            return

        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                patterns = f.readlines()

            self.gitignore_spec = pathspec.PathSpec.from_lines(
                pathspec.patterns.GitWildMatchPattern,
                patterns
            )
            logger.info(f"Loaded .gitignore from {gitignore_path}")
        except Exception as e:
            logger.warning(f"Failed to load .gitignore: {e}")

    def should_exclude_dir(self, dir_path: str | Path) -> bool:
        """
        判断目录是否应该被排除

        Args:
            dir_path: 目录路径

        Returns:
            是否应该排除
        """
        dir_path = Path(dir_path)
        dir_name = dir_path.name

        # 检查是否在排除列表中
        if dir_name in self.exclude_dirs:
            return True

        # 检查 .gitignore
        if self.gitignore_spec:
            try:
                if self.gitignore_spec.match_file(str(dir_path)):
                    return True
            except Exception:
                pass

        # 检查隐藏目录 (以 . 开头)
        if dir_name.startswith('.') and dir_name not in {'.', '..'}:
            return True

        return False

    def should_exclude_file(self, file_path: str | Path) -> bool:
        """
        判断文件是否应该被排除

        Args:
            file_path: 文件路径

        Returns:
            是否应该排除
        """
        file_path = Path(file_path)

        # 检查文件是否存在
        if not file_path.exists():
            return True

        # 检查文件大小
        try:
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size_bytes:
                logger.debug(f"File too large ({file_size} bytes): {file_path}")
                return True
            if file_size == 0:
                return True
        except Exception:
            return True

        # 检查文件模式
        file_name = file_path.name
        for pattern in self.exclude_patterns:
            if self._match_pattern(file_name, pattern):
                return True

        # 检查 .gitignore
        if self.gitignore_spec:
            try:
                if self.gitignore_spec.match_file(str(file_path)):
                    return True
            except Exception:
                pass

        return False

    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """
        简单的文件名模式匹配

        Args:
            filename: 文件名
            pattern: 模式 (支持 * 通配符)

        Returns:
            是否匹配
        """
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)

    def scan_directory(
        self,
        root_path: str | Path,
        max_depth: Optional[int] = None,
        include_extensions: Optional[Set[str]] = None
    ) -> Iterator[Path]:
        """
        扫描目录,返回符合条件的文件

        Args:
            root_path: 根目录路径
            max_depth: 最大扫描深度 (None 表示无限制)
            include_extensions: 只包含的文件扩展名集合 (None 表示全部)

        Yields:
            符合条件的文件路径
        """
        root_path = Path(root_path)

        if not root_path.exists() or not root_path.is_dir():
            logger.error(f"Invalid directory: {root_path}")
            return

        def _scan_recursive(current_path: Path, current_depth: int):
            """递归扫描"""
            # 检查深度限制
            if max_depth is not None and current_depth > max_depth:
                return

            try:
                entries = list(current_path.iterdir())
            except PermissionError:
                logger.warning(f"Permission denied: {current_path}")
                return
            except Exception as e:
                logger.warning(f"Error reading directory {current_path}: {e}")
                return

            for entry in entries:
                try:
                    if entry.is_dir():
                        # 处理目录
                        if not self.should_exclude_dir(entry):
                            yield from _scan_recursive(entry, current_depth + 1)

                    elif entry.is_file():
                        # 处理文件
                        if self.should_exclude_file(entry):
                            continue

                        # 检查扩展名过滤
                        if include_extensions:
                            if entry.suffix.lower() not in include_extensions:
                                continue

                        yield entry

                except Exception as e:
                    logger.debug(f"Error processing {entry}: {e}")

        yield from _scan_recursive(root_path, 0)

    def get_file_stats(self, files: List[Path]) -> dict:
        """
        获取文件统计信息

        Args:
            files: 文件路径列表

        Returns:
            统计信息字典
        """
        from collections import defaultdict

        stats = {
            'total_files': len(files),
            'by_extension': defaultdict(int),
            'total_size_bytes': 0,
            'by_category': defaultdict(int)
        }

        for file_path in files:
            try:
                # 统计扩展名
                ext = file_path.suffix.lower()
                stats['by_extension'][ext or 'no_extension'] += 1

                # 统计文件大小
                stats['total_size_bytes'] += file_path.stat().st_size

                # 统计类别
                category = self._get_file_category(ext)
                stats['by_category'][category] += 1

            except Exception as e:
                logger.debug(f"Error getting stats for {file_path}: {e}")

        return dict(stats)

    def _get_file_category(self, extension: str) -> str:
        """获取文件类别"""
        categories = {
            'code': {'.py', '.js', '.ts', '.java', '.go', '.rs', '.rb', '.php', '.c', '.cpp', '.cs'},
            'config': {'.json', '.yaml', '.yml', '.toml', '.xml', '.ini'},
            'docs': {'.md', '.rst', '.txt'},
            'web': {'.html', '.css', '.scss', '.sass'},
            'image': {'.png', '.jpg', '.jpeg', '.gif', '.svg'},
        }

        for category, exts in categories.items():
            if extension in exts:
                return category

        return 'other'
