"""
Claude 查询助手

提供带重试和JSON解析的统一查询接口
"""

import json
from typing import Dict, Any, Tuple, Optional, Callable
from .json_extractor import JSONExtractor


class ClaudeQueryHelper:
    """Claude查询助手 - 带重试和JSON解析"""

    @staticmethod
    async def _check_error_and_reconnect(
        client,
        message,
        attempt: int,
        max_attempts: int
    ) -> Tuple[bool, Optional[str]]:
        """
        检查消息是否包含错误，如果有错误则尝试重连

        Args:
            client: ClaudeSDKClient实例
            message: 接收到的消息
            attempt: 当前尝试次数
            max_attempts: 最大尝试次数

        Returns:
            (has_error, error_message) 元组
        """
        from claude_agent_sdk.types import ResultMessage

        # 检查是否为错误结果
        if isinstance(message, ResultMessage) and message.is_error:
            error_message = message.result or "未知错误"

            # 所有类型的错误（包括 Prompt too long）都尝试重连
            print(f"          ⚠️  Claude 返回错误: {error_message}")

            if attempt < max_attempts:
                print(f"          🔄 尝试重连 client 并重试 ({attempt}/{max_attempts-1})...")
                try:
                    # 重连 client
                    await client.disconnect()
                    await client.connect()
                    print(f"          ✓ Client 重连成功")
                except Exception as reconnect_error:
                    print(f"          ⚠️  重连失败: {reconnect_error}")

                return True, error_message
            else:
                raise RuntimeError(f"Claude 执行错误（尝试{max_attempts}次）: {error_message}")

        return False, None

    @staticmethod
    async def _execute_query_with_retry(
        client,
        prompt: str,
        session_id: str,
        max_attempts: int
    ) -> str:
        """
        执行查询并收集响应文本，带错误检测和重连重试

        Args:
            client: ClaudeSDKClient实例
            prompt: 提示词
            session_id: 会话ID
            max_attempts: 最大尝试次数

        Returns:
            响应文本

        Raises:
            RuntimeError: Claude 执行错误（达到最大重试次数）
        """
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                # 发送查询
                print(f"          🔍 发送查询: {session_id}")
                await client.query(prompt, session_id=session_id)

                # 接收响应
                response_text = ""
                has_error = False

                async for message in client.receive_response():
                    # 检查错误并处理重连
                    error_occurred, error_msg = await ClaudeQueryHelper._check_error_and_reconnect(
                        client, message, attempt, max_attempts
                    )

                    if error_occurred:
                        has_error = True
                        last_error = error_msg
                        break

                    # 收集响应文本
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                response_text += block.text

                # 如果有错误，跳到下一次重试
                if has_error:
                    continue

                # 成功返回
                return response_text

            except RuntimeError:
                # RuntimeError 是 _check_error_and_reconnect 抛出的，表示已达最大重试次数
                raise
            except Exception as e:
                last_error = str(e)
                if attempt < max_attempts:
                    print(f"          ⚠️  查询异常：{e}，重试 {attempt}/{max_attempts-1}...")
                    continue
                else:
                    print(f"          ❌ 查询异常：{e}，已达最大重试次数")
                    raise

        # 不应该到达这里
        raise RuntimeError(f"查询失败（尝试{max_attempts}次）：{last_error}")

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
            RuntimeError: Claude 执行错误（达到最大重试次数）
            ValueError: JSON 验证失败（达到最大重试次数）
        """
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                # 执行查询并获取响应文本
                response_text = await ClaudeQueryHelper._execute_query_with_retry(
                    client, prompt, session_id, max_attempts
                )

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
                    print(f"          🔍 验证失败的JSON结构: {json.dumps(parsed_json, ensure_ascii=False, indent=2)[:500]}...")
                    if attempt < max_attempts:
                        print(f"          ⚠️  JSON验证失败，重试 {attempt}/{max_attempts-1}...")
                        continue
                    else:
                        print(f"          ❌ JSON验证失败，已达最大重试次数")
                        raise ValueError(f"JSON验证失败（尝试{max_attempts}次）")

                # 成功
                return response_text, parsed_json

            except RuntimeError:
                # RuntimeError 来自 _execute_query_with_retry，直接抛出
                raise
            except ValueError:
                # ValueError 来自 JSON 验证失败，继续重试或抛出
                if attempt >= max_attempts:
                    raise
                continue
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
        session_id: str,
        max_attempts: int = 3
    ) -> str:
        """
        发送查询并返回纯文本响应（不解析JSON）

        Args:
            client: ClaudeSDKClient实例
            prompt: 提示词
            session_id: 会话ID
            max_attempts: 最大尝试次数（默认3次）

        Returns:
            响应文本

        Raises:
            RuntimeError: Claude 执行错误（达到最大重试次数）
        """
        # 直接调用核心方法
        return await ClaudeQueryHelper._execute_query_with_retry(
            client, prompt, session_id, max_attempts
        )

