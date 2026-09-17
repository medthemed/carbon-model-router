"""Shared fixtures for carbon-model-router tests."""

from __future__ import annotations

import pytest

from carbon_model_router.catalog import default_catalog
from carbon_model_router.types import Catalog, ModelSpec


@pytest.fixture
def catalog() -> Catalog:
    return default_catalog()


@pytest.fixture
def simple_prompt() -> str:
    return SIMPLE_PROMPT


@pytest.fixture
def complex_prompt() -> str:
    return COMPLEX_PROMPT


@pytest.fixture
def tiny_catalog() -> Catalog:
    return Catalog(
        models=[
            ModelSpec(
                id="tiny",
                name="Tiny",
                provider="local",
                cost_per_1k=0.0,
                energy_kwh_per_1k=0.00001,
                capability=0.40,
                max_tokens=2048,
            ),
            ModelSpec(
                id="big",
                name="Big",
                provider="hosted",
                cost_per_1k=0.01,
                energy_kwh_per_1k=0.01,
                capability=0.95,
                max_tokens=32768,
            ),
        ]
    )


SIMPLE_PROMPT = "What is the capital of France?"

COMPLEX_PROMPT = """\
Design a distributed consensus protocol for a multi-region payments system.

Requirements:
1. Survive minority partitions without split-brain
2. Provide linearizability for balance updates
3. Compare Raft vs Paxos trade-offs for this workload
4. Prove safety under asynchronous network assumptions
5. Outline a formal verification plan

Please produce:
- An architecture diagram description
- A step-by-step rollout plan
- Pseudocode for the leader election path
- A JSON schema for the replication log entry
"""
