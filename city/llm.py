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
