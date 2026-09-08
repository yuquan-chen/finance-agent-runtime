from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from finance_agent.config import Settings


Message = dict[str, str]


@dataclass(frozen=True)
class LlmToolCall:
    """A structured function call returned by the model."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LlmResponse:
    content: str
    provider: str
    model: str
    elapsed_ms: int
    raw: dict[str, Any]
    tool_calls: tuple[LlmToolCall, ...] = ()


class LlmProvider(Protocol):
    provider_name: str

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0,
        max_tokens: int = 1000,
        timeout_seconds: int | None = None,
    ) -> LlmResponse:
        ...

    def chat_json(
        self,
        messages: list[Message],
        *,
        temperature: float = 0,
        max_tokens: int = 1000,
        timeout_seconds: int | None = None,
    ) -> tuple[dict[str, Any], LlmResponse]:
        ...

    def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        temperature: float = 0,
        max_tokens: int = 1000,
        timeout_seconds: int | None = None,
    ) -> LlmResponse:
        ...


class OpenAICompatibleLlmProvider:
    provider_name = "lmstudio"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._json_format_supported: bool | None = None  # 缓存格式检测结果

    def _post_chat_completion(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        """Make a bounded retry for transient upstream transport failures."""
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        last_response: httpx.Response | None = None
        attempts = max(1, self.settings.lmstudio_retry_attempts)
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f"{self.settings.lmstudio_base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                last_response = response
            except httpx.TransportError:
                if attempt + 1 >= attempts:
                    raise
                time.sleep(0.4 * (attempt + 1))
                continue

            if response.status_code not in retryable_statuses or attempt + 1 >= attempts:
                return response
            time.sleep(0.4 * (attempt + 1))

        if last_response is None:
            raise RuntimeError("LLM request ended without a response")
        return last_response

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout_seconds: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LlmResponse:
        started = time.time()
        payload = {
            "model": self.settings.lmstudio_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format
        headers = {
            "Authorization": f"Bearer {self.settings.lmstudio_api_key}",
            "Content-Type": "application/json",
        }
        timeout = timeout_seconds or self.settings.lmstudio_timeout_seconds
        response = self._post_chat_completion(payload, headers, timeout)
        if response.status_code != 200:
            error_detail = response.text
            raise httpx.HTTPStatusError(
                f"LM Studio 返回错误: {response.status_code} - {error_detail}",
                request=response.request,
                response=response,
            )
        data = response.json()
        message = data["choices"][0]["message"]
        # DeepSeek 返回 reasoning_content 和 content，优先用 content
        content = message.get("content") or message.get("reasoning_content") or ""
        return LlmResponse(
            content=content,
            provider=self.provider_name,
            model=self.settings.lmstudio_model,
            elapsed_ms=int((time.time() - started) * 1000),
            raw=data,
        )

    def chat_json(
        self,
        messages: list[Message],
        *,
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[dict[str, Any], LlmResponse]:
        # DeepSeek 不支持 json_object（content 为空），直接用 text 模式
        # 如果以后换回支持 json_object 的模型，可以恢复尝试逻辑
        response = self._chat_with_text_fallback(messages, temperature, max_tokens, timeout_seconds)
        return extract_json_object(response.content), response

    def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout_seconds: int | None = None,
    ) -> LlmResponse:
        """Call an OpenAI-compatible endpoint using model-selected tools."""
        started = time.time()
        payload: dict[str, Any] = {
            "model": self.settings.lmstudio_model,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": "auto",
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.settings.lmstudio_api_key}",
            "Content-Type": "application/json",
        }
        timeout = timeout_seconds or self.settings.lmstudio_timeout_seconds
        response = self._post_chat_completion(payload, headers, timeout)
        if response.status_code != 200:
            error_detail = response.text
            raise httpx.HTTPStatusError(
                f"LM Studio 返回错误: {response.status_code} - {error_detail}",
                request=response.request,
                response=response,
            )
        data = response.json()

        message = data["choices"][0]["message"]
        calls: list[LlmToolCall] = []
        for index, item in enumerate(message.get("tool_calls") or []):
            function = item.get("function") or {}
            raw_arguments = function.get("arguments") or "{}"
            arguments = (
                json.loads(raw_arguments)
                if isinstance(raw_arguments, str)
                else raw_arguments
            )
            if not isinstance(arguments, dict):
                raise ValueError("LLM tool arguments must be a JSON object")
            calls.append(
                LlmToolCall(
                    call_id=str(item.get("id") or f"tool_call_{index + 1}"),
                    name=str(function.get("name") or ""),
                    arguments=arguments,
                )
            )
        return LlmResponse(
            content=message.get("content") or "",
            provider=self.provider_name,
            model=self.settings.lmstudio_model,
            elapsed_ms=int((time.time() - started) * 1000),
            raw=data,
            tool_calls=tuple(calls),
        )

    def _chat_with_text_fallback(
        self,
        messages: list[Message],
        temperature: float,
        max_tokens: int | None,
        timeout_seconds: int | None,
    ) -> LlmResponse:
        """text 模式调用，自动在 prompt 末尾加 JSON 输出提示。"""
        # 给 system prompt 加一句，引导 LLM 输出 JSON
        enhanced_messages = list(messages)
        if enhanced_messages and enhanced_messages[-1]["role"] == "user":
            enhanced_messages[-1] = {
                "role": "user",
                "content": enhanced_messages[-1]["content"] + "\n\n请直接输出 JSON，不要包含其他文字。",
            }
        return self.chat(
            enhanced_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )


def build_llm_provider(settings: Settings) -> LlmProvider:
    return OpenAICompatibleLlmProvider(settings)


def extract_json_object(text: str) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON 对象，兼容多种格式。"""
    if not text or not text.strip():
        raise ValueError("LLM 返回了空响应")

    stripped = text.strip()

    # 1. 直接是 JSON
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 2. 包裹在 markdown 代码块中: ```json ... ``` 或 ``` ... ```
    code_block = _extract_from_code_block(stripped)
    if code_block:
        try:
            return json.loads(code_block)
        except json.JSONDecodeError:
            pass

    # 3. 提取第一个 { ... } 块（兼容 LLM 在 JSON 前后加了文字）
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 输出中提取 JSON: {stripped[:200]}")


def _extract_from_code_block(text: str) -> str | None:
    """从 markdown 代码块中提取内容。"""
    import re
    # 匹配 ```json ... ``` 或 ``` ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    return match.group(1).strip() if match else None
