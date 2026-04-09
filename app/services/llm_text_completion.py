from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Optional

from loguru import logger

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from app.services.llm.litellm_provider import LiteLLMTextProvider


def _run_async_safely(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def run_in_new_loop():
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(run_in_new_loop).result()


def call_text_chat_completion(
    prompt: str,
    *,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    timeout: int = 120,
    log_label: str = "LLM",
) -> str:
    if not (api_key and model):
        return ""

    clean_base_url = str(base_url or "").strip()
    if requests and clean_base_url:
        url = clean_base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.warning("{} HTTP 调用失败，尝试回退 LiteLLM: {}", log_label, exc)

    try:
        provider = LiteLLMTextProvider(
            api_key=api_key,
            model_name=model,
            base_url=clean_base_url or None,
        )
        return _run_async_safely(
            provider.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
            )
        ).strip()
    except Exception as exc:
        logger.warning("{} LiteLLM 调用失败，回退规则路径: {}", log_label, exc)
        return ""
