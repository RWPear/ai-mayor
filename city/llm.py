"""One small Ollama client shared by every mind in the kingdom (king, warlord, subjects).

Environment:
  OLLAMA_URL          default http://localhost:11434
  OLLAMA_MODEL        the main model (king, warlord)        default qwen3:14b
  OLLAMA_CROWD_MODEL  model for subjects' intents (cheaper)  default: same as OLLAMA_MODEL
  OLLAMA_NUM_CTX      context size                           default 6144
"""
import json
import os
import re

import httpx


class LLM:
    def __init__(self, model=None, crowd=False):
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        main = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
        self.model = model or (os.environ.get("OLLAMA_CROWD_MODEL", main) if crowd else main)
        self.ctx = int(os.environ.get("OLLAMA_NUM_CTX", "6144"))
        self.calls = 0

    def chat(self, system, user, schema=None, max_tokens=900, temperature=0.8):
        body = {"model": self.model, "stream": False, "think": False, "keep_alive": "30m",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": temperature, "num_ctx": self.ctx, "num_predict": max_tokens}}
        if schema:
            body["format"] = schema
        with httpx.Client(timeout=300) as cl:
            r = cl.post(f"{self.url}/api/chat", json=body)
            if r.status_code == 400:          # older Ollama without the "think" switch
                body.pop("think", None)
                r = cl.post(f"{self.url}/api/chat", json=body)
            r.raise_for_status()
            text = r.json()["message"]["content"]
        self.calls += 1
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    def json(self, system, user, schema, max_tokens=900, temperature=0.8):
        return json.loads(self.chat(system, user, schema, max_tokens, temperature))
