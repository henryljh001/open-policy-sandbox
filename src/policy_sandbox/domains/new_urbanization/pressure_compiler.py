"""Compile registered pressure plugins into bounded aggregate and behavior effects."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from policy_sandbox.domains.new_urbanization.state import BaselineRates
from policy_sandbox.plugins.registry import PressureScenarioFactory


class PressureCompilationError(ValueError):
    """Raised when a pressure package is ambiguous or outside model bounds."""


@dataclass(frozen=True)
class CompiledPressurePackage:
    """Auditable result of compiling explicit synthetic pressure assumptions."""

    pressure_names: tuple[str, ...]
    rate_deltas: Mapping[str, float]
    behavior_deltas: Mapping[str, float]
    warnings: tuple[Mapping[str, str], ...] = field(default_factory=tuple)
    digest: str = ""

    def apply_to(self, baseline: BaselineRates) -> BaselineRates:
        """Apply pressure deltas and enforce aggregate rate bounds."""

        values = {name: float(value) for name, value in asdict(baseline).items()}
        for name, delta in self.rate_deltas.items():
            if name not in values:
                raise PressureCompilationError(f"Unknown baseline rate after pressure: {name}")
            values[name] += delta
        try:
            return BaselineRates.from_mapping(values)
        except (TypeError, ValueError) as exc:
            raise PressureCompilationError(str(exc)) from exc


def _digest(value: Mapping[str, Any]) -> str:
    """Return a stable digest for the complete pressure package."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compile_pressure_package(
    package: Mapping[str, Any],
    baseline: BaselineRates,
) -> CompiledPressurePackage:
    """Compile pressure configs and reject duplicates or hidden assumptions."""

    if package.get("synthetic") is not True:
        raise PressureCompilationError("pressure_package must set synthetic=true")
    entries = package.get("pressures")
    if not isinstance(entries, list):
        raise PressureCompilationError("pressure_package.pressures must be a list")
    identifiers: set[str] = set()
    names: set[str] = set()
    ordered_names: list[str] = []
    rate_deltas: dict[str, float] = {}
    behavior_deltas: dict[str, float] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise PressureCompilationError("each pressure must be an object")
        identifier = entry.get("pressure_id")
        name = entry.get("name")
        config = entry.get("config")
        if not isinstance(identifier, str) or not identifier:
            raise PressureCompilationError("pressure_id must be a non-empty string")
        if identifier in identifiers:
            raise PressureCompilationError(f"duplicate pressure_id: {identifier}")
        identifiers.add(identifier)
        if not isinstance(name, str) or not name:
            raise PressureCompilationError("pressure name must be a non-empty string")
        if name in names:
            raise PressureCompilationError(f"duplicate pressure name: {name}")
        names.add(name)
        ordered_names.append(name)
        if not isinstance(config, Mapping):
            raise PressureCompilationError(f"pressure config must be an object: {name}")
        try:
            effect = PressureScenarioFactory(name, config).compile()
        except (TypeError, ValueError) as exc:
            raise PressureCompilationError(f"{name}: {exc}") from exc
        for rate_name, delta in effect.rate_deltas.items():
            rate_deltas[rate_name] = rate_deltas.get(rate_name, 0.0) + delta
        for behavior_name, delta in effect.behavior_deltas.items():
            behavior_deltas[behavior_name] = (
                behavior_deltas.get(behavior_name, 0.0) + delta
            )
    warnings: list[Mapping[str, str]] = []
    if ordered_names:
        warnings.append(
            {
                "code": "SYNTHETIC_PRESSURE_ACTIVE",
                "severity": "warning",
                "message": "压力效应为显式合成假设，只用于稳健性和失效模式测试。",
            }
        )
    if len(ordered_names) >= 3:
        warnings.append(
            {
                "code": "COMBINED_PRESSURE_STACK",
                "severity": "warning",
                "message": "同时叠加三类以上压力，结果应按极端边界情景解释。",
            }
        )
    compiled = CompiledPressurePackage(
        pressure_names=tuple(ordered_names),
        rate_deltas=dict(sorted(rate_deltas.items())),
        behavior_deltas=dict(sorted(behavior_deltas.items())),
        warnings=tuple(warnings),
        digest=_digest(package),
    )
    compiled.apply_to(baseline)
    return compiled
