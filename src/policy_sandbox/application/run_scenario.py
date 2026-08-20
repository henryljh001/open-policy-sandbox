"""Run a scenario through a registered simulation engine."""

import hashlib
import json
from typing import Any, Mapping

from policy_sandbox.plugins import engines as _engines  # noqa: F401
from policy_sandbox.plugins.registry import SimulationEngineFactory


def _canonical_digest(value: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 digest for JSON-compatible input."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Run one validated scenario and construct an auditable result envelope.

    Args:
        scenario: JSON-compatible scenario matching a public Scenario schema.

    Returns:
        A JSON-compatible simulation run envelope.

    Raises:
        KeyError: If required scenario fields are absent.
        ValueError: If the configured engine is not registered.
    """

    input_digest = _canonical_digest(scenario)
    engine_spec = scenario["engine"]
    engine = SimulationEngineFactory(engine_spec["name"], engine_spec.get("config", {}))
    result = engine.run(scenario)
    return {
        "schema_version": "1.0.0",
        "run_id": f"run-{input_digest[:16]}",
        "scenario_id": scenario["scenario_id"],
        "scenario_version": scenario["version"],
        "input_digest": input_digest,
        "engine": {
            "name": engine.descriptor.name,
            "version": engine.descriptor.version,
            "config_digest": _canonical_digest(dict(engine_spec.get("config", {}))),
        },
        "random_seed": scenario["random_seed"],
        "started_at": None,
        "finished_at": None,
        "status": "succeeded",
        "outcomes": dict(result.outcomes),
        "group_outcomes": {
            group: dict(values) for group, values in result.group_outcomes.items()
        },
        "uncertainty": {},
        "warnings": list(result.warnings),
        "reproducible": True,
        "synthetic": bool(scenario.get("synthetic", False)),
    }
