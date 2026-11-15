"""Reads the followers list from Instagram's own "Download your information"
export (Accounts Center -> Your information and permissions -> Download your
information -> Followers and following, JSON format).

Point it at the unzipped export folder, the followers_*.json file, or the zip.
Handles both shapes Instagram has used:
  [{"string_list_data": [{"href": ..., "value": "username", "timestamp": ...}]}, ...]
  [{"title": "username", "string_list_data": [{"href": ..., "timestamp": ...}]}, ...]
"""
import json
import zipfile
from pathlib import Path


def _entries(data):
    if isinstance(data, dict):  # some exports wrap the list
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    return data


def _username(entry):
    for s in entry.get("string_list_data") or []:
        if s.get("value"):
            return s["value"]
        href = s.get("href", "")
        if href:
            return href.rstrip("/").split("/")[-1]
    return entry.get("title") or None


def _from_json_bytes(b):
    out = []
    for e in _entries(json.loads(b)):
        u = _username(e)
        if u:
            out.append(u.strip().lstrip("@").lower())
    return out


def read_followers(path):
    p = Path(path)
    names = []
    if p.suffix == ".zip":
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if Path(n).name.startswith("followers") and n.endswith(".json"):
                    names += _from_json_bytes(z.read(n))
    elif p.is_dir():
        for f in sorted(p.rglob("followers*.json")):
            names += _from_json_bytes(f.read_bytes())
    else:
        names = _from_json_bytes(p.read_bytes())
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def read_comments(path):
    """Comments file for one post: [{username, text, timestamp}] (what the API step will produce)."""
    return json.loads(Path(path).read_text())
