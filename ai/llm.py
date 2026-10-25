"""Thin LLM client. Uses the Anthropic Messages API when ANTHROPIC_API_KEY is set,
otherwise returns None so callers can fall back to offline logic (CI stays green
without secrets)."""
import json
import os
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"


def ask(prompt: str, system: str = "", max_tokens: int = 1500):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({
        "model": os.environ.get("LLM_MODEL", "claude-sonnet-5-5"),
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as exc:  # network/quota errors must not break the pipeline
        print(f"[ai] LLM call failed, using offline fallback: {exc}")
        return None
