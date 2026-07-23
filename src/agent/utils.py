"""
src/agent/utils.py —— 公共工具函数

解决 google-genai SDK 中 response.text 类型为 str | None 的问题。
所有需要访问响应文本的地方，统一走这里。
"""
from google.genai import types
from google.genai.types import GenerateContentResponse

def safe_text(response: GenerateContentResponse, default: str = "") -> str:
    """
    从 GenerateContentResponse 中安全提取文本。

    解决 response.text 类型为 str | None 的问题。
    返回时保证拿到 str，Pyright 不会报红。
    同时适用于普通调用和流式输出的 chunk（都是 GenerateContentResponse 类型）。

    Args:
        response: google.genai 的 GenerateContentResponse 对象
        default: 当 response.text 为 None 时返回的默认值

    Returns:
        文本内容（必定是 str，不会是 None）

    Examples:
        >>> resp = client.models.generate_content(...)
        >>> text = safe_text(resp)
        >>> print(text[:300])  # 安全：不会因为 None 而崩溃

        >>> for chunk in client.models.generate_content_stream(...):
        ...     text = safe_text(chunk)
        ...     if text:  # 可以安全判空
        ...         print(text, end="", flush=True)
    """
    if response.text is not None:
        return response.text
    return default

def safe_parts(content: types.Content) -> list[types.Part]:
    """
    从 Content 中安全获取 parts 列表。

    新版 SDK 中 content.parts 类型为 list[Part] | None。
    此函数提供安全的兜底：None 时返回空列表。

    Args:
        content: types.Content 对象（来自 chat.get_history()）

    Returns:
        parts 列表（必定是 list，不会是 None）

    Examples:
        >>> for msg in chat.get_history():
        ...     for part in safe_parts(msg):
        ...         if part.text:
        ...             print(part.text)
    """
    return content.parts or []