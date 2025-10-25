"""
JSON 提取工具

提供健壮的 JSON 解析功能，支持从各种格式的 AI 响应中提取 JSON 数据
"""

import json
import re
from typing import Dict, Any, Optional


class JSONExtractor:
    """JSON 提取器 - 从 AI 响应文本中提取 JSON 数据"""

    @staticmethod
    def extract(text: str, verbose: bool = False) -> Dict[str, Any]:
        """
        从响应文本中提取 JSON

        使用多种策略尝试提取 JSON：
        1. 直接解析整个文本
        2. 查找 ```json 代码块（取最后一个）
        3. 查找所有 ``` 代码块（不限语言，取最后一个）
        4. 使用栈匹配找最后一个完整的 JSON 对象

        Args:
            text: 响应文本
            verbose: 是否输出详细日志

        Returns:
            提取的 JSON 对象，如果失败返回空字典
        """
        if not text or not text.strip():
            if verbose:
                print("  ⚠️  响应文本为空")
            return {}

        # 策略1: 尝试直接解析整个文本
        try:
            result = json.loads(text.strip())
            if verbose:
                print("  ✓ 策略1成功: 直接解析整个文本")
            return result
        except json.JSONDecodeError:
            pass

        # 策略2: 查找所有 ```json 代码块，取最后一个（使用贪婪匹配）
        json_blocks = re.findall(r'```json\s*(\{.*\})\s*```', text, re.DOTALL)
        if json_blocks:
            # 从后往前尝试每个代码块
            for block in reversed(json_blocks):
                try:
                    result = json.loads(block)
                    if verbose:
                        print(f"  ✓ 策略2成功: 从 {len(json_blocks)} 个 ```json 代码块中提取")
                    return result
                except json.JSONDecodeError:
                    continue

        # 策略3: 查找所有 ``` 代码块（不限语言），取最后一个（使用贪婪匹配）
        code_blocks = re.findall(r'```(?:\w+)?\s*(\{.*\})\s*```', text, re.DOTALL)
        if code_blocks:
            # 从后往前尝试每个代码块
            for block in reversed(code_blocks):
                try:
                    result = json.loads(block)
                    if verbose:
                        print(f"  ✓ 策略3成功: 从 {len(code_blocks)} 个代码块中提取")
                    return result
                except json.JSONDecodeError:
                    continue

        # 策略4: 使用栈匹配找所有完整的 JSON 对象，取最后一个有效的
        json_candidates = []
        stack = []
        start_idx = -1

        for i, char in enumerate(text):
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append('{')
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start_idx != -1:
                        # 找到一个完整的花括号对
                        json_candidates.append((start_idx, i + 1))
                        start_idx = -1

        # 从后往前尝试每个候选
        for start, end in reversed(json_candidates):
            try:
                result = json.loads(text[start:end])
                if verbose:
                    print(f"  ✓ 策略4成功: 使用栈匹配提取 JSON 对象（从{len(json_candidates)}个候选中）")
                return result
            except json.JSONDecodeError:
                continue

        # 所有策略都失败
        if verbose:
            print("  ⚠️  无法从响应中提取有效 JSON")
            print(f"     响应内容预览: {text[:200]}...")

        return {}

    @staticmethod
    def try_extract(text: str, verbose: bool = False) -> Optional[Dict[str, Any]]:
        """
        尝试提取 JSON，失败返回 None 而不是空字典

        Args:
            text: 响应文本
            verbose: 是否输出详细日志

        Returns:
            提取的 JSON 对象，如果失败返回 None
        """
        result = JSONExtractor.extract(text, verbose)
        return result if result else None

    @staticmethod
    def extract_with_fallback(
        text: str,
        fallback: Dict[str, Any],
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        提取 JSON，失败时使用指定的回退值

        Args:
            text: 响应文本
            fallback: 失败时的回退值
            verbose: 是否输出详细日志

        Returns:
            提取的 JSON 对象，如果失败返回 fallback
        """
        result = JSONExtractor.extract(text, verbose)
        return result if result else fallback

