"""AWS Bedrock backend for hosts/loop.py. Optional: only used when AWS credentials exist.
Uses the Anthropic SDK's Bedrock Mantle client (Messages API on Bedrock)."""

from __future__ import annotations

from ledger import config


def configured() -> bool:
    return bool(config.get("AWS_REGION") and (config.get("AWS_ACCESS_KEY_ID") or config.get("AWS_PROFILE")))


def complete(system: str, messages: list[dict], max_tokens: int = 4096) -> tuple[str, dict]:
    from anthropic import AnthropicBedrockMantle

    client = AnthropicBedrockMantle(aws_region=config.get("AWS_REGION"))
    response = client.messages.create(
        model=config.get("BEDROCK_MODEL_ID") or "anthropic.claude-opus-5",
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return text, {"prompt_tokens": response.usage.input_tokens, "completion_tokens": response.usage.output_tokens}
