"""Heuristic prompt complexity analyzer.

Produces a 0-1 complexity score and a required capability level from
deterministic text signals. No model calls.
"""

from __future__ import annotations

import re

from carbon_model_router.types import ComplexityScore

# Signal weights (should sum to 1.0 for the score)
WEIGHT_LENGTH = 0.20
WEIGHT_CODE = 0.20
WEIGHT_MATH = 0.15
WEIGHT_MULTI_STEP = 0.20
WEIGHT_DOMAIN = 0.15
WEIGHT_FORMAT = 0.10

# Capability mapping: score → required capability, piecewise linear
# 0.0 → 0.25, 0.4 → 0.45, 0.6 → 0.65, 0.8 → 0.80, 1.0 → 0.95
_CAPABILITY_BREAKPOINTS: tuple[tuple[float, float], ...] = (
    (0.0, 0.25),
    (0.4, 0.45),
    (0.6, 0.65),
    (0.8, 0.80),
    (1.0, 0.95),
)

_CODE_FENCE = re.compile(r"```|^\s{4}\S|^\t\S", re.MULTILINE)
_MATH = re.compile(
    r"(?:\b(?:integral|derivative|theorem|proof|lemma|matrix|eigenvalue)\b"
    r"|\$[^$]+\$"
    r"|\\frac|\\sum|\\int"
    r"|\b\d+\s*[+\-*/^]\s*\d+"
    r"|\bsolve\b|\bprove\b|\boptimize\b)",
    re.IGNORECASE,
)
_MULTI_STEP = re.compile(
    r"(?:\bstep[- ]by[- ]step\b"
    r"|\bfirst\b.*\bthen\b"
    r"|\bsecondly\b|\bfinally\b"
    r"|\bafter that\b"
    r"|\bcompare and\b"
    r"|\btrade-?offs?\b"
    r"|\bdesign\b.*\barchitecture\b"
    r"|\brefactor\b"
    r"|\bimplement\b.*\btest\b"
    r"|^\s*\d+\.\s+\S)",
    re.IGNORECASE | re.DOTALL,
)
_DOMAIN = re.compile(
    r"\b(?:distributed|consensus|raft|paxos|kubernetes|compiler|type theory"
    r"|category theory|cryptography|post-quantum|formal verification"
    r"|race condition|deadlock|cap theorem|linearizability"
    r"|machine learning|transformer|attention|gradient"
    r"|microservices|event sourcing|cqrs)\b",
    re.IGNORECASE,
)
_FORMAT = re.compile(
    r"(?:\bjson\b|\byaml\b|\bschema\b|\btable\b"
    r"|\bmarkdown\b|\bsql\b|\bregex\b"
    r"|\boutput format\b|\bmust return\b)",
    re.IGNORECASE,
)

# Simple intents that stay cheap even if a bit long
_SIMPLE_INTENT = re.compile(
    r"^(?:hi|hello|hey|thanks|thank you|ok|okay|yes|no)\b"
    r"|\bwhat is\b.+\?"
    r"|\bdefine\b"
    r"|\bsynonym\b"
    r"|\btranslate\b"
    r"|\brewrite\b"
    r"|\bsummarize\b.+\bin one (?:sentence|line)\b"
    r"|\blist (?:the )?(?:three|3|five|5) \w+\b",
    re.IGNORECASE,
)

# Prompt-domain overrides. Floors raise a signal when the caller already knows
# the domain; chat applies a soft complexity cap for chatty prompts.
VALID_DOMAINS = ("code", "math", "chat")
_DOMAIN_SIGNAL_FLOORS: dict[str, tuple[str, float]] = {
    "code": ("code", 0.55),
    "math": ("math", 0.55),
}
_CHAT_SOFT_CAP = 0.35
_CHAT_HARD_SIGNAL = 0.30


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def length_signal(text: str) -> tuple[float, str | None]:
    """0 at <80 chars, 1.0 at >= 1200 chars."""
    n = len(text)
    if n < 80:
        return 0.0, None
    if n >= 1200:
        return 1.0, f"long prompt ({n} chars)"
    score = (n - 80) / (1200 - 80)
    return score, None


def code_signal(text: str) -> tuple[float, str | None]:
    fences = len(re.findall(r"```", text))
    fence_pairs = fences // 2
    indented = len(_CODE_FENCE.findall(text))
    lang_markers = len(
        re.findall(r"\b(?:def |class |import |function |const |let |var |public |private)\b", text)
    )
    raw = fence_pairs * 0.4 + min(indented, 10) * 0.05 + min(lang_markers, 10) * 0.05
    score = clamp01(raw)
    reason = f"code signals (fences={fence_pairs}, markers={lang_markers})" if score > 0.15 else None
    return score, reason


def math_signal(text: str) -> tuple[float, str | None]:
    hits = len(_MATH.findall(text))
    score = clamp01(hits / 4.0)
    reason = f"math/formal markers ({hits})" if score > 0.15 else None
    return score, reason


def multi_step_signal(text: str) -> tuple[float, str | None]:
    hits = len(_MULTI_STEP.findall(text))
    bullets = len(re.findall(r"^\s*[-*+]\s+\S", text, re.MULTILINE))
    numbered = len(re.findall(r"^\s*\d+\.\s+\S", text, re.MULTILINE))
    raw = hits * 0.35 + min(bullets, 8) * 0.08 + min(numbered, 8) * 0.08
    score = clamp01(raw)
    reason = f"multi-step structure (markers={hits}, bullets={bullets})" if score > 0.15 else None
    return score, reason


def domain_signal(text: str) -> tuple[float, str | None]:
    hits = len(set(m.group(0).lower() for m in _DOMAIN.finditer(text)))
    score = clamp01(hits / 3.0)
    reason = f"domain keywords ({hits})" if score > 0.15 else None
    return score, reason


def format_signal(text: str) -> tuple[float, str | None]:
    hits = len(_FORMAT.findall(text))
    score = clamp01(hits / 3.0)
    reason = f"structured-output requests ({hits})" if score > 0.15 else None
    return score, reason


def score_to_capability(score: float) -> float:
    """Piecewise-linear map from complexity score to required capability."""
    s = clamp01(score)
    points = _CAPABILITY_BREAKPOINTS
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= s <= x1:
            if x1 == x0:
                return y1
            t = (s - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return points[-1][1]


def analyze_prompt(text: str, domain: str | None = None) -> ComplexityScore:
    """Analyze prompt text and return complexity + required capability.

    ``domain`` optionally forces the prompt domain: ``code``, ``math``, or
    ``chat``. Code/math raise the matching signal floor so short-but-hard
    prompts are not under-routed. Chat applies a soft complexity cap so
    chatty prompts stay on small models unless other hard signals dominate.
    """
    if text is None:
        text = ""
    stripped = text.strip()

    if domain is not None and domain not in VALID_DOMAINS:
        raise ValueError(
            f"invalid domain {domain!r}; expected one of {', '.join(VALID_DOMAINS)}"
        )

    signals: dict[str, float] = {}
    reasons: list[str] = []

    pairs = {
        "length": length_signal(stripped),
        "code": code_signal(stripped),
        "math": math_signal(stripped),
        "multi_step": multi_step_signal(stripped),
        "domain": domain_signal(stripped),
        "format": format_signal(stripped),
    }
    for key, (value, reason) in pairs.items():
        signals[key] = value
        if reason:
            reasons.append(reason)

    # Domain floors applied before the weighted sum
    if domain in _DOMAIN_SIGNAL_FLOORS:
        signal_name, floor = _DOMAIN_SIGNAL_FLOORS[domain]
        if signals[signal_name] < floor:
            signals[signal_name] = floor
        reasons.append(f"domain override: {domain}")

    weighted = (
        WEIGHT_LENGTH * signals["length"]
        + WEIGHT_CODE * signals["code"]
        + WEIGHT_MATH * signals["math"]
        + WEIGHT_MULTI_STEP * signals["multi_step"]
        + WEIGHT_DOMAIN * signals["domain"]
        + WEIGHT_FORMAT * signals["format"]
    )
    score = clamp01(weighted)

    # Simple intents get a soft cap even if length is high
    if stripped and _SIMPLE_INTENT.search(stripped) and score > 0.35:
        score = min(score, 0.35)
        reasons.append("simple-intent cap applied")

    # Chat domain: keep chatty prompts cheap unless code/math dominate
    if domain == "chat":
        if (
            signals["code"] < _CHAT_HARD_SIGNAL
            and signals["math"] < _CHAT_HARD_SIGNAL
            and score > _CHAT_SOFT_CAP
        ):
            score = min(score, _CHAT_SOFT_CAP)
            reasons.append("domain override: chat (soft cap)")
        else:
            reasons.append("domain override: chat")

    # Empty / near-empty prompts are trivial
    if len(stripped) < 3:
        score = 0.0
        reasons.append("empty prompt")

    required = score_to_capability(score)
    return ComplexityScore(
        score=round(score, 4),
        required_capability=round(required, 4),
        signals={k: round(v, 4) for k, v in signals.items()},
        reasons=tuple(reasons),
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars/token, with a floor of 1 for non-empty."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)


__all__ = [
    "VALID_DOMAINS",
    "analyze_prompt",
    "clamp01",
    "code_signal",
    "domain_signal",
    "estimate_tokens",
    "format_signal",
    "length_signal",
    "math_signal",
    "multi_step_signal",
    "score_to_capability",
]
