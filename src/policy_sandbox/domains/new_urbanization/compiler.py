"""Compile registered policy levers into bounded annual-rate assumptions."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from policy_sandbox.domains.new_urbanization.state import BaselineRates
from policy_sandbox.plugins.registry import PolicyInterventionFactory


class PolicyCompilationError(ValueError):
    """Raised when a policy package is ambiguous, conflicting, or out of bounds."""


@dataclass(frozen=True)
class CompiledPolicyPackage:
    """Auditable result of compiling a synthetic policy package."""

    intervention_names: tuple[str, ...]
    rate_deltas: Mapping[str, float]
    tracked_adjustments: Mapping[str, float]
    warnings: tuple[Mapping[str, str], ...] = field(default_factory=tuple)
    digest: str = ""

    def apply_to(self, baseline: BaselineRates) -> BaselineRates:
        """Apply compiled deltas and enforce BaselineRates bounds."""

        values = {name: float(value) for name, value in asdict(baseline).items()}
        for name, delta in self.rate_deltas.items():
            if name not in values:
                raise PolicyCompilationError(f"Unknown baseline rate after compilation: {name}")
            values[name] += delta
        try:
            return BaselineRates.from_mapping(values)
        except (TypeError, ValueError) as exc:
            raise PolicyCompilationError(str(exc)) from exc


def _digest(value: Mapping[str, Any]) -> str:
    """Return a stable digest for the complete policy package."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compile_policy_package(
    package: Mapping[str, Any],
    baseline: BaselineRates,
) -> CompiledPolicyPackage:
    """Compile intervention configs and reject ambiguous combinations."""

    if package.get("synthetic") is not True:
        raise PolicyCompilationError("policy_package must set synthetic=true")
    entries = package.get("interventions")
    if not isinstance(entries, list):
        raise PolicyCompilationError("policy_package.interventions must be a list")

    identifiers: set[str] = set()
    names: set[str] = set()
    ordered_names: list[str] = []
    rate_deltas: dict[str, float] = {}
    tracked_adjustments: dict[str, float] = {}

    for entry in entries:
        if not isinstance(entry, Mapping):
            raise PolicyCompilationError("each intervention must be an object")
        identifier = entry.get("intervention_id")
        name = entry.get("name")
        config = entry.get("config")
        if not isinstance(identifier, str) or not identifier:
            raise PolicyCompilationError("intervention_id must be a non-empty string")
        if identifier in identifiers:
            raise PolicyCompilationError(f"duplicate intervention_id: {identifier}")
        identifiers.add(identifier)
        if not isinstance(name, str) or not name:
            raise PolicyCompilationError("intervention name must be a non-empty string")
        if name in names:
            raise PolicyCompilationError(f"duplicate intervention name: {name}")
        names.add(name)
        ordered_names.append(name)
        if not isinstance(config, Mapping):
            raise PolicyCompilationError(f"intervention config must be an object: {name}")

        try:
            effect = PolicyInterventionFactory(name, config).compile()
        except (TypeError, ValueError) as exc:
            raise PolicyCompilationError(f"{name}: {exc}") from exc
        for rate_name, delta in effect.rate_deltas.items():
            rate_deltas[rate_name] = rate_deltas.get(rate_name, 0.0) + delta
        for adjustment_name, delta in effect.tracked_adjustments.items():
            tracked_adjustments[adjustment_name] = (
                tracked_adjustments.get(adjustment_name, 0.0) + delta
            )

    warnings: list[Mapping[str, str]] = []
    support_names = {
        "resident_based_service_eligibility",
        "skills_and_employment_support",
        "affordable_housing",
        "county_service_expansion",
    }
    if "settlement_threshold" in names and not names.intersection(support_names):
        warnings.append(
            {
                "code": "SETTLEMENT_WITHOUT_CAPACITY_SUPPORT",
                "severity": "warning",
                "message": "落户放宽未同时配置就业、住房或公共服务支持。",
            }
        )
    capital_delta = rate_deltas.get("capital_expenditure_share", 0.0)
    land_delta = rate_deltas.get("construction_land_growth_rate", 0.0)
    if (
        (capital_delta >= 0.1 or land_delta >= 0.01)
        and "skills_and_employment_support" not in names
    ):
        warnings.append(
            {
                "code": "CAPACITY_WITHOUT_EMPLOYMENT_LINKAGE",
                "severity": "warning",
                "message": "高强度扩容未配置就业吸纳工具，需检查空置与债务风险。",
            }
        )
    if "citizenization_transfer" in names and not names.intersection(
        {"settlement_threshold", "resident_based_service_eligibility"}
    ):
        warnings.append(
            {
                "code": "TRANSFER_WITHOUT_ABSORPTION_RULE",
                "severity": "info",
                "message": "转移支付未与落户或常住人口服务规则组合。",
            }
        )

    compiled = CompiledPolicyPackage(
        intervention_names=tuple(ordered_names),
        rate_deltas=dict(sorted(rate_deltas.items())),
        tracked_adjustments=dict(sorted(tracked_adjustments.items())),
        warnings=tuple(warnings),
        digest=_digest(package),
    )
    compiled.apply_to(baseline)
    return compiled

