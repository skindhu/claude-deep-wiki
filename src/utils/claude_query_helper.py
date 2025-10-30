"""
Claude 查询助手

提供带重试和JSON解析的统一查询接口
"""

from typing import Dict, Any, Tuple, Optional, Callable
from .json_extractor import JSONExtractor


class ClaudeQueryHelper:
    """Claude查询助手 - 带重试和JSON解析"""

    @staticmethod
    async def query_with_json_retry(
        client,
        prompt: str,
        session_id: str,
        max_attempts: int = 3,
        validator: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        发送查询并解析JSON，失败时自动重试

        Args:
            client: ClaudeSDKClient实例
            prompt: 提示词
            session_id: 会话ID
            max_attempts: 最大尝试次数（默认3次）
            validator: 可选的验证函数，接收解析后的dict，返回bool

        Returns:
            (response_text, parsed_json) 元组

        Raises:
            ValueError: 达到最大重试次数仍失败
        """
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                # 发送查询
                await client.query(prompt, session_id=session_id)

                # 接收响应
                response_text = ""
                async for message in client.receive_response():
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                response_text += block.text

                # 提取JSON
                parsed_json = JSONExtractor.extract(response_text)

                # 检查是否提取到有效JSON
                if not parsed_json:
                    last_error = "JSON提取失败：返回空字典"
                    if attempt < max_attempts:
                        print(f"          ⚠️  JSON提取失败，重试 {attempt}/{max_attempts-1}...")
                        continue
                    else:
                        print(f"          ❌ JSON提取失败，已达最大重试次数")
                        raise ValueError(f"JSON提取失败（尝试{max_attempts}次）")

                # 如果提供了验证器，执行验证
                if validator and not validator(parsed_json):
                    last_error = "JSON验证失败：不符合预期格式"
                    if attempt < max_attempts:
                        print(f"          ⚠️  JSON验证失败，重试 {attempt}/{max_attempts-1}...")
                        continue
                    else:
                        print(f"          ❌ JSON验证失败，已达最大重试次数")
                        raise ValueError(f"JSON验证失败（尝试{max_attempts}次）")

                # 成功
                return response_text, parsed_json

            except Exception as e:
                last_error = str(e)
                if attempt < max_attempts:
                    print(f"          ⚠️  查询异常：{e}，重试 {attempt}/{max_attempts-1}...")
                    continue
                else:
                    print(f"          ❌ 查询异常：{e}，已达最大重试次数")
                    raise

        # 不应该到达这里，但为了类型检查
        raise ValueError(f"查询失败（尝试{max_attempts}次）：{last_error}")

    @staticmethod
    async def query_with_text(
        client,
        prompt: str,
        session_id: str
    ) -> str:
        """
        发送查询并返回纯文本响应（不解析JSON）

        Args:
            client: ClaudeSDKClient实例
            prompt: 提示词
            session_id: 会话ID

        Returns:
            响应文本
        """
        # 发送查询
        await client.query(prompt, session_id=session_id)

        # 接收响应
        response_text = ""
        async for message in client.receive_response():
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        response_text += block.text

        return response_text

