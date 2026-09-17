"""Tests for --domain override (code|math|chat)."""

from __future__ import annotations

import json

import pytest

from carbon_model_router.analyzer import VALID_DOMAINS, analyze_prompt
from carbon_model_router.cli import EXIT_OK, main
from carbon_model_router.router import route_prompt


def test_valid_domains_constant():
    assert set(VALID_DOMAINS) == {"code", "math", "chat"}


def test_domain_code_raises_code_signal():
    score = analyze_prompt("fix this off-by-one", domain="code")
    assert score.signals["code"] >= 0.55
    assert any("domain override: code" in r for r in score.reasons)


def test_domain_code_beats_auto_for_short_prompt():
    auto = analyze_prompt("fix this off-by-one")
    forced = analyze_prompt("fix this off-by-one", domain="code")
    assert forced.score > auto.score
    assert forced.required_capability > auto.required_capability


def test_domain_math_raises_math_signal():
    score = analyze_prompt("short lemma about continuity", domain="math")
    assert score.signals["math"] >= 0.55
    assert any("domain override: math" in r for r in score.reasons)


def test_domain_chat_soft_caps_chatty_prompt():
    chatty = (
        "Please help me polish this Slack message. Keep it friendly. "
        + ("Filler sentence about tone and wording. " * 40)
        + "\n- one\n- two\n- three\n- four\n- five\n- six\n"
        "First we do this. Then we do that. After that we wrap up. Finally we send it."
    )
    auto = analyze_prompt(chatty)
    forced = analyze_prompt(chatty, domain="chat")
    assert auto.score > 0.35
    assert forced.score <= 0.35
    assert any("chat" in r for r in forced.reasons)


def test_domain_chat_leaves_hard_signals_alone():
    hard = (
        "```python\ndef raft_leader_election(term, votes):\n"
        "    # prove safety under partial synchrony\n"
        "    return term\n```\n"
        + ("Distributed consensus details follow. " * 30)
    )
    forced = analyze_prompt(hard, domain="chat")
    # code floor is high, so chat cap should not crush it below auto
    auto = analyze_prompt(hard)
    assert forced.score >= auto.score - 0.05


def test_invalid_domain_raises():
    with pytest.raises(ValueError, match="invalid domain"):
        analyze_prompt("hello", domain="nope")


def test_route_prompt_accepts_domain():
    decision = route_prompt("fix this bug", domain="code")
    assert any("domain override" in r for r in decision.complexity.reasons)
    assert decision.model.id  # still returns a model


def test_cli_route_domain_flag(capsys):
    code = main(["route", "fix this off-by-one", "--domain", "code", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["complexity"]["signals"]["code"] >= 0.55
    assert any("domain override" in r for r in payload["complexity"]["reasons"])


def test_cli_analyze_domain_flag(capsys):
    code = main(["analyze", "short lemma", "--domain", "math", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["signals"]["math"] >= 0.55


def test_cli_route_without_domain_unchanged(capsys):
    code = main(["route", "What is the capital of France?", "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"]["id"]
    assert not any(
        "domain override" in r for r in payload["complexity"].get("reasons", [])
    )
