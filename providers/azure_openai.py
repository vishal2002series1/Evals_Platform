"""
Azure OpenAI provider for the evaluation runner.

Requires:
    pip install openai>=1.0.0

Environment variables:
    AZURE_OPENAI_ENDPOINT="https://<your-resource>.cognitiveservices.azure.com/"
    AZURE_OPENAI_API_KEY="..."
    AZURE_OPENAI_API_VERSION="2024-12-01-preview"
    AZURE_OPENAI_DEFAULT_DEPLOYMENT="gpt-4o"
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI


class AzureOpenAIProvider:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        default_deployment: Optional[str] = None,
    ):
        # Load from environment variables if not provided
        endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self.default_deployment = default_deployment or os.getenv("AZURE_OPENAI_DEFAULT_DEPLOYMENT")

        if not endpoint or not api_key:
            raise ValueError(
                "Missing Azure OpenAI credentials. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."
            )

        # Create Azure OpenAI client
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )

    def chat(
        self,
        deployment: Optional[str],
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> str:
        deployment_name = deployment or self.default_deployment
        if not deployment_name:
            raise ValueError("No deployment name provided. Set model_name or AZURE_OPENAI_DEFAULT_DEPLOYMENT.")

        kwargs: Dict[str, Any] = {
            "model": deployment_name,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if top_p:
            kwargs["top_p"] = top_p
        if seed:
            kwargs["seed"] = seed

        response = self.client.chat.completions.create(**kwargs)
        return (response.choices[0].message.content or "").strip()


def azure_chat_completion(provider_cfg: Dict[str, Any], prompt: str) -> str:
    """Execute Azure OpenAI chat completion."""
    provider = AzureOpenAIProvider(
        endpoint=provider_cfg.get("endpoint"),
        api_key=provider_cfg.get("api_key"),
        api_version=provider_cfg.get("api_version"),
        default_deployment=provider_cfg.get("default_deployment"),
    )

    messages = [{"role": "user", "content": prompt}]

    return provider.chat(
        deployment=provider_cfg.get("model_name"),
        messages=messages,
        temperature=float(provider_cfg.get("temperature", 0.0)),
        max_tokens=provider_cfg.get("max_tokens"),
        top_p=provider_cfg.get("top_p"),
        seed=provider_cfg.get("seed"),
    )