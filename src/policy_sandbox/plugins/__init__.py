"""Plugin protocols, registries, factories, and built-in discovery."""

from policy_sandbox.plugins.registry import (
    DOMAIN_REGISTRY,
    ENGINE_REGISTRY,
    INTERVENTION_REGISTRY,
    PRESSURE_REGISTRY,
    DomainPluginFactory,
    PolicyInterventionFactory,
    PressureScenarioFactory,
    SimulationEngineFactory,
    available_domains,
    available_engines,
    available_interventions,
    available_pressures,
    register_domain,
    register_engine,
    register_intervention,
    register_pressure,
)

from policy_sandbox.plugins import domains as _domains  # noqa: E402,F401
from policy_sandbox.plugins import engines as _engines  # noqa: E402,F401
from policy_sandbox.plugins import interventions as _interventions  # noqa: E402,F401
from policy_sandbox.plugins import pressures as _pressures  # noqa: E402,F401

__all__ = [
    "DOMAIN_REGISTRY",
    "ENGINE_REGISTRY",
    "INTERVENTION_REGISTRY",
    "PRESSURE_REGISTRY",
    "DomainPluginFactory",
    "PolicyInterventionFactory",
    "PressureScenarioFactory",
    "SimulationEngineFactory",
    "available_domains",
    "available_engines",
    "available_interventions",
    "available_pressures",
    "register_domain",
    "register_engine",
    "register_intervention",
    "register_pressure",
]
