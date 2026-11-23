"""One small Ollama client shared by every mind in the kingdom (king, warlord, subjects).

Environment:
  OLLAMA_URL          default http://localhost:11434
  OLLAMA_MODEL        the main model (king, warlord)        default qwen3:14b
  OLLAMA_CROWD_MODEL  model for subjects' intents (cheaper)  default: same as OLLAMA_MODEL
  OLLAMA_NUM_CTX      context size                           default 6144
"""
import collections
import itertools
import json
import os
import re
import sys
import time

import httpx

# every call, for anyone who wants to look inside (./kingdom play shows them as "Aldric's mind")
CALLS = collections.deque(maxlen=400)
_N = itertools.count()
CLOCK = None            # set by whoever runs the world: a function giving the game time


def _caller():
    """Which part of the kingdom is asking: the first frame outside this file (e.g. agents._two_step)."""
    f = sys._getframe(2)
    while f and f.f_code.co_filename.endswith(("llm.py",)):
        f = f.f_back
    names = []
    while f and len(names) < 2:
        mod = os.path.splitext(os.path.basename(f.f_code.co_filename))[0]
        if f.f_code.co_name not in ("json", "chat", "_ask") or mod != "llm":
            names.append(f"{mod}.{f.f_code.co_name}")
        f = f.f_back
    return names[0] if names else "?"


class LLM:
    def __init__(self, model=None, crowd=False):
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        main = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
        self.model = model or (os.environ.get("OLLAMA_CROWD_MODEL", main) if crowd else main)
        self.ctx = int(os.environ.get("OLLAMA_NUM_CTX", "6144"))
        self.calls = 0

    def chat(self, system, user, schema=None, max_tokens=900, temperature=0.8):
        rec = {"n": next(_N), "who": _caller(), "model": self.model, "time": CLOCK() if CLOCK else "",
               "system": system, "user": user, "temperature": temperature, "response": None, "error": None}
        t0 = time.time()
        try:
            text = self._chat(system, user, schema, max_tokens, temperature)
            rec["response"] = text
            return text
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            raise
        finally:
            rec["ms"] = int((time.time() - t0) * 1000)
            CALLS.append(rec)

    def _chat(self, system, user, schema=None, max_tokens=900, temperature=0.8):
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
