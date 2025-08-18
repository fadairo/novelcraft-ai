#!/usr/bin/env python3
"""
Anthropic API smoke test.

Usage:
  # PowerShell (set env var for this session)
  #   $Env:ANTHROPIC_API_KEY = "sk-ant-xxxxxxxx"
  #   python anthropic_smoke_test.py
  #
  # Optional flags:
  #   --model claude-3-5-sonnet-20240620   # override model
  #   --stream                              # test streaming API
"""

import os
import sys
import argparse
import asyncio
from anthropic import AsyncAnthropic

DEFAULT_MODEL = "claude-3-5-sonnet-20240620"

def fail(msg: str, code: int = 1):
    print(f"[FAIL] {msg}")
    sys.exit(code)

async def test_non_stream(client: AsyncAnthropic, model: str):
    print("[INFO] Running non-streaming test…")
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with OK"}],
        )
        text = resp.content[0].text if resp and resp.content else ""
        if "OK" in text.upper():
            print("[PASS] Non-streaming message succeeded:", text.strip())
        else:
            print("[PASS] Non-streaming call returned:", text.strip())
    except Exception as e:
        fail(f"Non-streaming call error: {repr(e)}")

async def test_stream(client: AsyncAnthropic, model: str):
    print("[INFO] Running streaming test…")
    try:
        full = []
        async with client.messages.stream(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with OK"}],
        ) as stream:
            async for chunk in stream.text_stream:
                full.append(chunk)
        text = "".join(full)
        if "OK" in text.upper():
            print("[PASS] Streaming message succeeded:", text.strip())
        else:
            print("[PASS] Streaming call returned:", text.strip())
    except Exception as e:
        fail(f"Streaming call error: {repr(e)}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--stream", action="store_true",
                        help="Also test streaming endpoint")
    args = parser.parse_args()

    key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        fail("ANTHROPIC_API_KEY is not set in the environment.")
    if not key.startswith("sk-ant-"):
        print("[WARN] ANTHROPIC_API_KEY does not look like an Anthropic key (expected 'sk-ant-…').")

    print("[INFO] Key prefix:", key[:6] + "…")
    print("[INFO] Model:", args.model)

    client = AsyncAnthropic(api_key=key)

    await test_non_stream(client, args.model)
    if args.stream:
        await test_stream(client, args.model)

    print("[DONE] Smoke test completed successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Aborted by user.")
