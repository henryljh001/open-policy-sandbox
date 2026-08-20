"""Run a traceable calibration assessment through a registered data adapter."""

import hashlib
import json
from typing import Any, Mapping

from policy_sandbox.adapters import AggregateDataAdapterFactory
from policy_sandbox.application.run_experiment import run_experiment
from policy_sandbox.domains.new_urbanization.microsim.calibration import (
    assess_calibration,
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_calibration(
    scenario: Mapping[str, Any],
    aggregate_dataset: Mapping[str, Any],
    *,
    adapter_name: str,
    adapter_config: Mapping[str, Any] | None = None,
    repetitions: int = 20,
    base_seed: int = 20260819,
) -> dict[str, Any]:
    """Assess synthetic aggregate targets without claiming empirical U6 passage."""

    if scenario.get("synthetic") is not True:
        raise ValueError("run_calibration currently accepts only synthetic=true scenarios")
    adapter = AggregateDataAdapterFactory(adapter_name, adapter_config or {})
    adapted = adapter.adapt(aggregate_dataset)
    if adapted.get("synthetic") is not True:
        raise ValueError("Demo calibration requires a synthetic adapter result")
    experiment = run_experiment(
        scenario,
        repetitions=repetitions,
        base_seed=base_seed,
    )
    targets = adapted["calibration_targets"]
    simulated = {
        outcome: float(experiment["outcome_summary"][outcome]["mean"])
        for outcome in targets
    }
    assessment = assess_calibration(simulated, targets)
    request = {
        "scenario_digest": _digest(scenario),
        "dataset_digest": adapted["input_digest"],
        "adapter": adapted["adapter"],
        "adapter_config": dict(adapter_config or {}),
        "repetitions": repetitions,
        "base_seed": base_seed,
    }
    input_digest = _digest(request)
    warnings = list(adapted["warnings"])
    warnings.extend(
        [
            {
                "code": "SYNTHETIC_CALIBRATION_FIXTURE",
                "severity": "warning",
                "message": "Calibration targets are synthetic integration fixtures.",
            },
            {
                "code": "U6_NOT_PASSED",
                "severity": "warning",
                "message": "This run does not establish real-data calibration validity.",
            },
        ]
    )
    return {
        "schema_version": "1.0.0",
        "calibration_id": f"calibration-{input_digest[:16]}",
        "status": (
            "synthetic_fixture_passed"
            if assessment["all_passed"]
            else "synthetic_fixture_failed"
        ),
        "input_digest": input_digest,
        "scenario_id": scenario["scenario_id"],
        "scenario_input_digest": request["scenario_digest"],
        "experiment_id": experiment["experiment_id"],
        "experiment_input_digest": experiment["input_digest"],
        "adapter": adapted["adapter"],
        "dataset_id": adapted["dataset_id"],
        "dataset_input_digest": adapted["input_digest"],
        "data_card_digest": adapted["data_card_digest"],
        "repetitions": repetitions,
        "base_seed": base_seed,
        "calibration_targets": targets,
        "target_provenance": adapted["target_provenance"],
        "assessment": assessment,
        "warnings": warnings,
        "U6_status": "not_passed",
        "reproducible": True,
        "usage_level": "Demo",
        "synthetic": True,
    }
