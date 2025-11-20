"""
Token 计数器 - 使用 tiktoken 精确统计 token 数量

支持 Claude 和 OpenAI 模型的 token 统计
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 尝试导入 tiktoken
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken 未安装，将使用粗略估算。安装方法: pip install tiktoken")


class TokenCounter:
    """Token 计数器"""

    # Claude 模型映射到对应的 encoding
    # Claude 使用与 GPT-4 相同的 tokenizer (cl100k_base)
    MODEL_ENCODINGS = {
        'claude-3-5-sonnet-20241022': 'cl100k_base',
        'claude-3-5-sonnet-20240620': 'cl100k_base',
        'claude-3-opus-20240229': 'cl100k_base',
        'claude-3-sonnet-20240229': 'cl100k_base',
        'claude-3-haiku-20240307': 'cl100k_base',
        'gpt-4': 'cl100k_base',
        'gpt-4-turbo': 'cl100k_base',
        'gpt-3.5-turbo': 'cl100k_base',
    }

    def __init__(self, model: str = 'claude-3-5-sonnet-20241022'):
        """
        初始化 Token 计数器

        Args:
            model: 模型名称，默认为 Claude 3.5 Sonnet
        """
        self.model = model
        self.encoding = None

        if TIKTOKEN_AVAILABLE:
            try:
                # 获取对应的 encoding
                encoding_name = self.MODEL_ENCODINGS.get(model, 'cl100k_base')
                self.encoding = tiktoken.get_encoding(encoding_name)
                logger.info(f"Token 计数器初始化成功，使用 encoding: {encoding_name}")
            except Exception as e:
                logger.error(f"初始化 tiktoken encoding 失败: {e}")
                self.encoding = None

    def count_tokens(self, text: str) -> int:
        """
        精确计算文本的 token 数量

        Args:
            text: 要统计的文本

        Returns:
            token 数量
        """
        if not text:
            return 0

        if self.encoding:
            try:
                tokens = self.encoding.encode(text)
                return len(tokens)
            except Exception as e:
                logger.error(f"Token 计数失败，使用估算: {e}")
                return self._estimate_tokens(text)
        else:
            return self._estimate_tokens(text)

    def count_tokens_with_details(self, text: str) -> dict:
        """
        计算 token 并返回详细信息

        Args:
            text: 要统计的文本

        Returns:
            {
                "tokens": int,
                "characters": int,
                "method": "precise" | "estimated",
                "char_per_token": float
            }
        """
        char_count = len(text)
        token_count = self.count_tokens(text)
        method = "precise" if self.encoding else "estimated"
        char_per_token = char_count / token_count if token_count > 0 else 0

        return {
            "tokens": token_count,
            "characters": char_count,
            "method": method,
            "char_per_token": round(char_per_token, 2)
        }

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        粗略估算 token 数量

        英文: 1 token ≈ 4 字符
        中文: 1 token ≈ 1.5-2 字符
        混合: 取中间值

        Args:
            text: 文本

        Returns:
            估算的 token 数量
        """
        if not text:
            return 0

        # 统计中文字符数
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        total_chars = len(text)
        english_chars = total_chars - chinese_chars

        # 中文按 1.5 字符 = 1 token，英文按 4 字符 = 1 token
        estimated = (chinese_chars / 1.5) + (english_chars / 4)

        return int(estimated)

    def format_stats(self, text: str, prefix: str = "") -> str:
        """
        格式化输出 token 统计信息

        Args:
            text: 要统计的文本
            prefix: 输出前缀

        Returns:
            格式化的统计字符串
        """
        details = self.count_tokens_with_details(text)

        method_icon = "🎯" if details["method"] == "precise" else "📏"

        return (
            f"{prefix}{method_icon} Token 统计: {details['tokens']:,} tokens "
            f"({details['characters']:,} 字符, "
            f"{details['char_per_token']:.1f} 字符/token)"
        )


# 全局单例
_global_counter: Optional[TokenCounter] = None


def get_token_counter(model: str = 'claude-3-5-sonnet-20241022') -> TokenCounter:
    """
    获取全局 Token 计数器实例

    Args:
        model: 模型名称

    Returns:
        TokenCounter 实例
    """
    global _global_counter
    if _global_counter is None or _global_counter.model != model:
        _global_counter = TokenCounter(model)
    return _global_counter


def count_tokens(text: str, model: str = 'claude-3-5-sonnet-20241022') -> int:
    """
    快捷函数：计算文本的 token 数量

    Args:
        text: 要统计的文本
        model: 模型名称

    Returns:
        token 数量
    """
    counter = get_token_counter(model)
    return counter.count_tokens(text)


def format_token_stats(text: str, model: str = 'claude-3-5-sonnet-20241022', prefix: str = "") -> str:
    """
    快捷函数：格式化输出 token 统计信息

    Args:
        text: 要统计的文本
        model: 模型名称
        prefix: 输出前缀

    Returns:
        格式化的统计字符串
    """
    counter = get_token_counter(model)
    return counter.format_stats(text, prefix)


# 使用示例
if __name__ == "__main__":
    # 测试文本
    test_texts = [
        "Hello, world! This is a test.",
        "你好，世界！这是一个测试。",
        "混合文本 Mixed text 测试 test",
        "def hello():\n    print('Hello, world!')\n    return True"
    ]

    counter = TokenCounter()

    print("=" * 60)
    print("Token 统计测试")
    print("=" * 60)

    for text in test_texts:
        print(f"\n文本: {text}")
        details = counter.count_tokens_with_details(text)
        print(f"  Tokens: {details['tokens']}")
        print(f"  字符数: {details['characters']}")
        print(f"  方法: {details['method']}")
        print(f"  字符/token: {details['char_per_token']}")
        print(f"  {counter.format_stats(text, prefix='  ')}")

    # 测试大文本
    print("\n" + "=" * 60)
    print("大文本测试 (200k tokens)")
    print("=" * 60)

    if TIKTOKEN_AVAILABLE:
        # 生成约 200k tokens 的文本
        large_text = "Hello world! " * 60000  # 约 180k tokens
        stats = counter.count_tokens_with_details(large_text)
        print(f"Token 数: {stats['tokens']:,}")
        print(f"字符数: {stats['characters']:,}")
        print(f"方法: {stats['method']}")
    else:
        print("请安装 tiktoken 进行精确测试: pip install tiktoken")

