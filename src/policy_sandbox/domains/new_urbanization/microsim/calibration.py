"""Framework-neutral calibration interface for aggregate moment targets."""

import math
from typing import Any, Mapping


def _number(value: Any, name: str) -> float:
    """Parse a finite numeric calibration value."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def assess_calibration(
    simulated: Mapping[str, float],
    targets: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare simulated aggregate moments with explicit target tolerances.

    Args:
        simulated: Named model outcomes.
        targets: Per-moment target, tolerance, and absolute/relative mode.

    Returns:
        JSON-compatible pass details. The caller owns target provenance.
    """

    details: dict[str, dict[str, float | str | bool]] = {}
    passed = 0
    for name, specification in targets.items():
        if name not in simulated:
            raise ValueError(f"Calibration target is not a simulated outcome: {name}")
        if not isinstance(specification, Mapping):
            raise TypeError(f"calibration target {name} must be an object")
        unknown = sorted(set(specification) - {"target", "tolerance", "mode"})
        if unknown:
            raise ValueError(f"Unknown calibration fields for {name}: {', '.join(unknown)}")
        target = _number(specification.get("target"), f"{name}.target")
        tolerance = _number(specification.get("tolerance"), f"{name}.tolerance")
        if tolerance < 0:
            raise ValueError(f"{name}.tolerance must be non-negative")
        mode = specification.get("mode", "absolute")
        if mode not in {"absolute", "relative"}:
            raise ValueError(f"{name}.mode must be absolute or relative")
        actual = _number(simulated[name], name)
        absolute_error = abs(actual - target)
        if mode == "relative":
            denominator = max(abs(target), 1e-12)
            evaluated_error = absolute_error / denominator
        else:
            evaluated_error = absolute_error
        moment_passed = evaluated_error <= tolerance
        passed += int(moment_passed)
        details[name] = {
            "simulated": actual,
            "target": target,
            "absolute_error": absolute_error,
            "evaluated_error": evaluated_error,
            "tolerance": tolerance,
            "mode": str(mode),
            "passed": moment_passed,
        }
    total = len(details)
    return {
        "all_passed": total > 0 and passed == total,
        "passed": passed,
        "total": total,
        "pass_rate_pct": passed / total * 100.0 if total else 0.0,
        "moments": details,
    }
