"""Deterministic additive engine for testing the framework, not policy effects."""

import math
from typing import Any, Mapping

from policy_sandbox.domain.models import EngineDescriptor, SimulationResult
from policy_sandbox.plugins.base import SimulationEngine
from policy_sandbox.plugins.registry import register_engine


@register_engine("deterministic_baseline")
class DeterministicBaselineEngine(SimulationEngine):
    """Add numeric intervention parameters to matching baseline outcomes.

    This engine exists only to validate contracts, registration, orchestration,
    and reproducibility. It does not encode a real behavioral or causal model.
    """

    descriptor = EngineDescriptor(name="deterministic_baseline", version="0.1.0")

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        super().__init__(cfg)
        self.effect_parameter = str(cfg.get("effect_parameter", "parameters"))

    def run(self, scenario: Mapping[str, Any]) -> SimulationResult:
        """Apply simple additive effects to a numeric baseline."""

        baseline = scenario.get("baseline", {})
        outcomes: dict[str, float] = {}
        for name, value in baseline.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f"baseline.{name} must be finite")
                outcomes[str(name)] = number

        for intervention in scenario.get("interventions", []):
            effects = intervention.get(self.effect_parameter, {})
            for name, value in effects.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    number = float(value)
                    if not math.isfinite(number):
                        raise ValueError(f"intervention.{name} must be finite")
                    updated = outcomes.get(str(name), 0.0) + number
                    if not math.isfinite(updated):
                        raise ValueError(f"outcome.{name} must remain finite")
                    outcomes[str(name)] = updated

        warning = {
            "code": "SYNTHETIC_BASELINE_ONLY",
            "severity": "warning",
            "message": "确定性加法引擎仅验证软件链路，不代表真实政策效果。",
        }
        return SimulationResult(outcomes=outcomes, warnings=(warning,))
