"""Tests for the prompt complexity analyzer."""

from __future__ import annotations

from carbon_model_router.analyzer import (
    analyze_prompt,
    estimate_tokens,
    score_to_capability,
)
from tests.conftest import COMPLEX_PROMPT, SIMPLE_PROMPT


def test_simple_prompt_low_complexity():
    score = analyze_prompt(SIMPLE_PROMPT)
    assert 0.0 <= score.score <= 0.35
    assert score.required_capability <= 0.50


def test_complex_prompt_high_complexity():
    score = analyze_prompt(COMPLEX_PROMPT)
    assert score.score >= 0.50
    assert score.required_capability >= 0.55


def test_complexity_bounds():
    for text in ["", "a", "x" * 5000, SIMPLE_PROMPT, COMPLEX_PROMPT]:
        score = analyze_prompt(text)
        assert 0.0 <= score.score <= 1.0
        assert 0.0 <= score.required_capability <= 1.0


def test_code_fence_increases_score():
    plain = analyze_prompt("Please help me with a short note.")
    code = analyze_prompt(
        "Please help me with this code:\n```python\ndef f(x):\n    return x + 1\n```\n"
    )
    assert code.score > plain.score
    assert code.signals["code"] > plain.signals["code"]


def test_math_signal_detected():
    score = analyze_prompt("Prove that the integral of x^2 is x^3/3 using the theorem.")
    assert score.signals["math"] > 0.2


def test_multi_step_signal_detected():
    score = analyze_prompt(
        "First, gather requirements. Then design the schema. "
        "Secondly implement migrations. Finally write tests."
    )
    assert score.signals["multi_step"] > 0.2


def test_domain_keywords_detected():
    score = analyze_prompt(
        "Explain linearizability and how Raft handles consensus under partition."
    )
    assert score.signals["domain"] > 0.2


def test_empty_prompt_is_zero():
    score = analyze_prompt("   ")
    assert score.score == 0.0


def test_score_to_capability_monotonic():
    prev = -1.0
    for s in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        cap = score_to_capability(s)
        assert cap >= prev
        prev = cap
    assert score_to_capability(0.0) <= 0.30
    assert score_to_capability(1.0) >= 0.90


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") >= 1
    assert estimate_tokens("x" * 400) == 100


def test_deterministic():
    a = analyze_prompt(COMPLEX_PROMPT)
    b = analyze_prompt(COMPLEX_PROMPT)
    assert a == b
