# -*- coding: utf-8 -*-
"""DeepSeek 调用（OpenAI 兼容接口，JSON 输出）。"""

import json
import os
import re
import time

import requests

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"


def _loads(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def chat_json(system, user, temperature=0.7, max_tokens=4000):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    last_err = None
    for attempt in (1, 2):
        try:
            r = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=240,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return _loads(content)
        except Exception as exc:  # 重试一次再放弃，让 job 失败可见
            last_err = exc
            if attempt == 1:
                time.sleep(5)
    raise RuntimeError(f"DeepSeek 调用失败：{last_err}")
