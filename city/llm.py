"""One small model client shared by every mind in Emberfall (king, warlord, the people, the narrator).

Local (Ollama) by default. Settings go in .env next to ./kingdom (never in git):
  OLLAMA_URL          default: found automatically (this machine, localhost or its network address)
  OLLAMA_MODEL        the main model (king, warlord)                  default qwen3:14b
  OLLAMA_CROWD_MODEL  model for the people's comments                 default: same as OLLAMA_MODEL
  OLLAMA_NUM_CTX      context size                                    default 6144

Optional: a hosted model for the comments (reading them, writing replies, talk, the world's narration) - the
part people actually read. Aldric's own thinking stays local. Off unless COMMENT_MODEL is set:
  COMMENT_MODEL       e.g. claude-sonnet-5-5 (Anthropic) or any OpenAI-compatible model name
  ANTHROPIC_API_KEY   for claude-* models
  OPENAI_API_KEY      for anything else, with OPENAI_BASE_URL (default https://api.openai.com/v1; OpenRouter,
                      Groq and others work too)
  COMMENT_MAX_CALLS   a day's budget of hosted calls before it falls back to the local model (default 1500)
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


_FOUND = {}


def find_ollama():
    """Where Ollama answers: OLLAMA_URL if set, else this machine (localhost, then its own network addresses -
    Ollama is often bound to the LAN address only, e.g. OLLAMA_HOST=192.168.1.23)."""
    if "url" in _FOUND:
        return _FOUND["url"]
    if os.environ.get("OLLAMA_URL"):
        _FOUND["url"] = os.environ["OLLAMA_URL"].rstrip("/")
        return _FOUND["url"]
    import socket
    hosts = ["localhost", "127.0.0.1"]
    try:
        hosts += [a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # the address this machine uses on the network
        s.connect(("10.255.255.255", 1))
        hosts.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    for h in dict.fromkeys(hosts):
        try:
            if httpx.get(f"http://{h}:11434/api/tags", timeout=1.5).status_code == 200:
                _FOUND["url"] = f"http://{h}:11434"
                return _FOUND["url"]
        except httpx.HTTPError:
            continue
    _FOUND["url"] = "http://localhost:11434"
    return _FOUND["url"]


def check(url=None, model=None):
    """Is the model there? -> {"ok", "url", "model", "error"}"""
    url = (url or find_ollama()).rstrip("/")
    model = model or os.environ.get("OLLAMA_MODEL", "qwen3:14b")
    try:
        r = httpx.get(f"{url}/api/tags", timeout=4)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        if not any(n == model or n.split(":")[0] == model.split(":")[0] and model in n for n in names):
            return {"ok": False, "url": url, "model": model,
                    "error": f"Ollama is there, but it doesn't have {model} (it has: {', '.join(names[:6]) or 'nothing'})"
                             f". Run: ollama pull {model}"}
        return {"ok": True, "url": url, "model": model, "error": None}
    except Exception as e:
        return {"ok": False, "url": url, "model": model,
                "error": f"Ollama isn't answering at {url} ({type(e).__name__}: {e}). Set OLLAMA_URL in .env "
                         f"(e.g. OLLAMA_URL=http://192.168.1.23:11434)."}


class LLM:
    def __init__(self, model=None, crowd=False):
        self.url = find_ollama()
        main = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
        self.model = model or (os.environ.get("OLLAMA_CROWD_MODEL", main) if crowd else main)
        self.ctx = int(os.environ.get("OLLAMA_NUM_CTX", "6144"))
        self.calls = 0

    def chat(self, system, user, schema=None, max_tokens=900, temperature=0.8):
        """max_tokens is how long an answer is expected to be, not a guillotine: the model gets plenty of room
        (the prompt and the schema keep it short), and if it still runs out, it's asked again with more."""
        room = max(max_tokens * 3, 1536) if schema else max(max_tokens * 2, 400)
        rec = {"n": next(_N), "who": _caller(), "model": self.model, "time": CLOCK() if CLOCK else "",
               "system": system, "user": user, "temperature": temperature, "response": None, "error": None}
        t0 = time.time()
        try:
            text, why = self._chat(system, user, schema, room, temperature)
            if why == "length" and schema:            # ran out of room mid-answer: once more, with lots
                rec["retried"] = f"ran out of room at {room} tokens; asked again with {room * 3}"
                text, why = self._chat(system, user, schema, room * 3, temperature)
            if why == "length" and not schema:        # prose: end on the last whole sentence
                cut = max(text.rfind(". "), text.rfind("! "), text.rfind("? "), text.rfind(".\n"))
                text = text[:cut + 1] if cut > 20 else text
            rec["response"] = text
            rec["done"] = why
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
            j = r.json()
            text = j["message"]["content"]
        self.calls += 1
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip(), j.get("done_reason", "stop")

    def json(self, system, user, schema, max_tokens=900, temperature=0.8):
        """A structured answer. If it doesn't come back as valid JSON, the model gets one more go before anyone
        falls back to rules."""
        for attempt in (1, 2):
            text = self.chat(system, user, schema, max_tokens, temperature)
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                if CALLS and CALLS[-1].get("response") == text:
                    CALLS[-1]["error"] = ("the answer wasn't valid JSON" + (" - asking again" if attempt == 1 else
                                          " twice - the game falls back to rules for this one") + f" ({e})")
                if attempt == 2:
                    raise


class APILLM(LLM):
    """A hosted model with the same interface (chat / json). Claude models go to the Anthropic API; anything else to
    an OpenAI-compatible API. If it fails or the day's budget is spent, the local model answers instead."""

    def __init__(self, model):
        self.model = model
        self.calls = 0
        self.anthropic = model.startswith("claude")
        self.key = os.environ.get("ANTHROPIC_API_KEY" if self.anthropic else "OPENAI_API_KEY", "")
        self.base = ("https://api.anthropic.com/v1" if self.anthropic
                     else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.max_calls = int(os.environ.get("COMMENT_MAX_CALLS", "1500"))
        self.today = (time.strftime("%Y-%m-%d"), 0)
        self.local = LLM(crowd=True)

    def _chat(self, system, user, schema=None, max_tokens=900, temperature=0.8):
        day, n = self.today
        if day != time.strftime("%Y-%m-%d"):
            day, n = time.strftime("%Y-%m-%d"), 0
        if n >= self.max_calls or not self.key:     # out of budget (or no key): the local model answers
            return self.local._chat(system, user, schema, max_tokens, temperature)
        self.today = (day, n + 1)
        try:
            out = self._anthropic(system, user, schema, max_tokens, temperature) if self.anthropic else \
                self._openai(system, user, schema, max_tokens, temperature)
            self.calls += 1
            return out
        except Exception:
            return self.local._chat(system, user, schema, max_tokens, temperature)

    def _anthropic(self, system, user, schema, max_tokens, temperature):
        body = {"model": self.model, "max_tokens": min(max_tokens, 8000), "temperature": min(1.0, temperature),
                "system": system, "messages": [{"role": "user", "content": user}]}
        if schema:                                  # a forced tool call always comes back as valid JSON
            body["tools"] = [{"name": "answer", "description": "Your answer.", "input_schema": schema}]
            body["tool_choice"] = {"type": "tool", "name": "answer"}
        r = httpx.post(f"{self.base}/messages", json=body, timeout=120,
                       headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        j = r.json()
        why = "length" if j.get("stop_reason") == "max_tokens" else "stop"
        for block in j.get("content", []):
            if schema and block.get("type") == "tool_use":
                return json.dumps(block.get("input", {})), why
        return "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text").strip(), why

    def _openai(self, system, user, schema, max_tokens, temperature):
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}}
        r = httpx.post(f"{self.base}/chat/completions", json=body, timeout=120,
                       headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()
        ch = r.json()["choices"][0]
        return (ch["message"].get("content") or "").strip(), ("length" if ch.get("finish_reason") == "length" else "stop")


def comment_llm():
    """The model for the comments: the hosted one if COMMENT_MODEL is set (and has a key), else the local one."""
    m = os.environ.get("COMMENT_MODEL", "").strip()
    if m:
        api = APILLM(m)
        if api.key:
            return api
        print(f"!!! COMMENT_MODEL is {m}, but there's no {'ANTHROPIC_API_KEY' if api.anthropic else 'OPENAI_API_KEY'}"
              f" in .env - the comments stay on the local model.")
    return LLM(crowd=True)
