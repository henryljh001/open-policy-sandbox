"""New urbanization domain declaration and configuration checks."""

from typing import Any, Mapping

from policy_sandbox.domain.models import DomainDescriptor
from policy_sandbox.plugins.base import DomainPlugin
from policy_sandbox.plugins.registry import register_domain

ALLOWED_FOCUS_MODULES = {
    "citizenization",
    "potential_region",
    "metropolitan_area",
    "urban_renewal_resilience",
    "integrated",
}
ALLOWED_SCALES = {"county", "prefecture", "metropolitan_area", "province"}
ALLOWED_MODULES = {
    "population",
    "labor",
    "housing",
    "public_service",
    "fiscal",
    "land",
    "mobility",
    "governance",
    "resilience",
}


@register_domain("new_urbanization")
class NewUrbanizationDomain(DomainPlugin):
    """Declare the new urbanization policy domain without fixing an engine."""

    descriptor = DomainDescriptor(
        name="new_urbanization",
        version="0.3.0",
        title="新型城镇化",
        status="demo",
        supported_scales=("county", "prefecture", "metropolitan_area", "province"),
        supported_time_steps=("annual",),
    )

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        super().__init__(cfg)
        issues = self.validate_config()
        if issues:
            raise ValueError("Invalid new_urbanization config: " + "; ".join(issues))

    def policy_dimensions(self) -> tuple[str, ...]:
        """Return the domain's stable policy dimensions."""

        return (
            "citizenization",
            "employment_and_industry",
            "housing_and_public_service",
            "spatial_system_and_mobility",
            "fiscal_and_land",
            "governance_and_resilience",
        )

    def validate_config(self) -> tuple[str, ...]:
        """Validate domain-level configuration without reading private data."""

        issues: list[str] = []
        focus = self.cfg.get("focus_module")
        scale = self.cfg.get("spatial_scale")
        time_step = self.cfg.get("time_step")
        horizon = self.cfg.get("horizon_years")
        modules = self.cfg.get("enabled_modules")

        if focus not in ALLOWED_FOCUS_MODULES:
            issues.append(f"unsupported focus_module: {focus}")
        if scale not in ALLOWED_SCALES:
            issues.append(f"unsupported spatial_scale: {scale}")
        if time_step != "annual":
            issues.append("time_step must be annual in version 0.3.0")
        if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 15:
            issues.append("horizon_years must be an integer between 1 and 15")
        if not isinstance(modules, list) or not modules:
            issues.append("enabled_modules must be a non-empty list")
        elif unknown := sorted(set(modules) - ALLOWED_MODULES):
            issues.append("unsupported enabled_modules: " + ", ".join(unknown))
        if self.cfg.get("synthetic") is not True:
            issues.append("demo examples must set synthetic=true")

        return tuple(issues)

