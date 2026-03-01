"""
utils/bedrock.py
════════════════
Thin wrapper around AWS Bedrock for Claude Sonnet 4.6.
Both agents import this to avoid duplicating the boto3 setup.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import json
import logging
import re
import boto3
from botocore.config import Config

from config import (
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    AWS_SESSION_TOKEN, AWS_REGION, BEDROCK_MODEL_ID
)

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            service_name="bedrock-runtime",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN,
            config=Config(read_timeout=90, connect_timeout=15),
        )
        logger.info("[Bedrock] ✅ Client created")
    return _client


def invoke(system_prompt: str, user_message: str,
           max_tokens: int = 2048, temperature: float = 0.9) -> str:
    """
    Call Claude on Bedrock and return the raw text response.
    Strips any accidental ```json fences.
    """
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }

    logger.info(f"[Bedrock] Calling {BEDROCK_MODEL_ID} (temp={temperature})…")
    client = get_client()
    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload),
    )
    body = json.loads(response["body"].read())
    text = body["content"][0]["text"].strip()

    # DEBUG — remove after fixing
    logger.info(f"[Bedrock] RAW RESPONSE: {repr(text[:500])}")

    # Strip markdown code fences if model accidentally adds them
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text


def invoke_json(system_prompt: str, user_message: str,
                max_tokens: int = 2048, temperature: float = 0.4) -> dict:
    """
    Like invoke(), but parses the response as JSON and returns a dict.
    Handles partial responses, extra text, truncation, and bad characters.
    """
    raw = invoke(system_prompt, user_message, max_tokens, temperature)

    # 1. Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Find the FIRST complete { ... } block only
    try:
        start = raw.index("{")
        # Walk forward counting braces to find the matching closing brace
        depth = 0
        end = start
        for i, ch in enumerate(raw[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # 3. Response may be truncated — try to close it and parse what we have
    try:
        start = raw.index("{")
        chunk = raw[start:]
        # Count open braces to determine how many closing braces to add
        open_count = chunk.count("{") - chunk.count("}")
        # Remove trailing comma or incomplete field if present
        chunk = chunk.rstrip().rstrip(",")
        # Close any open string
        if chunk.count('"') % 2 != 0:
            chunk += '"'
        chunk += "}" * max(open_count, 1)
        return json.loads(chunk)
    except Exception as e:
        logger.error(f"[Bedrock] JSON parse failed after all attempts.\nRaw: {raw}\nError: {e}")
        # Return a safe fallback so the bot doesn't crash
        return {
            "intent": "unknown",
            "amount": None,
            "currency": None,
            "category": None,
            "item_name": None,
            "expense_date": None,
            "day_of_week": None,
            "time_of_day": None,
            "note": raw[:200],
            "language": "en",
            "split_info": None,
            "raw_text": user_message,
            "confidence": 0.0
        }