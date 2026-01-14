from __future__ import annotations
import re
from dataclasses import dataclass

_URL_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"discord\.gg/\w+", re.IGNORECASE),
    re.compile(r"discord\.com/invite/\w+", re.IGNORECASE),
    re.compile(r"\bbit\.ly\b|\bt\.co\b|\bgoo\.gl\b", re.IGNORECASE),
    # domain-ish (conservative)
    re.compile(r"\b[a-z0-9][a-z0-9\-]{0,62}\.[a-z]{2,}\b", re.IGNORECASE),
]

_MENTION_PATTERNS = [
    re.compile(r"@everyone", re.IGNORECASE),
    re.compile(r"@here", re.IGNORECASE),
    re.compile(r"<@!?\d+>"),  # user mention
    re.compile(r"<@&\d+>"),   # role mention
]

@dataclass(frozen=True)
class FieldLimits:
    name: int = 32
    condition: int = 60
    hobby: int = 60
    care: int = 80
    one: int = 60

LIMITS = FieldLimits()

def contains_link(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and any(p.search(t) for p in _URL_PATTERNS)

def contains_mention(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and any(p.search(t) for p in _MENTION_PATTERNS)

def first_violating_field_length(name: str, condition: str, hobby: str, care: str, one: str) -> str | None:
    if len(name) > LIMITS.name:
        return "名前"
    if len(condition) > LIMITS.condition:
        return "診断名/入場条件"
    if len(hobby) > LIMITS.hobby:
        return "趣味"
    if len(care) > LIMITS.care:
        return "配慮して欲しい事"
    if len(one) > LIMITS.one:
        return "自由に一言"
    return None
