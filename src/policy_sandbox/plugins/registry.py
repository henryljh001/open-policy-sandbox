"""Plugin registries, factories, and auto-discovery helpers."""

import importlib
import pkgutil
from collections.abc import Callable, Iterable
from types import ModuleType
from typing import Any, Mapping, TypeVar

from policy_sandbox.plugins.base import (
    DomainPlugin,
    PolicyIntervention,
    PressureScenario,
    SimulationEngine,
)

EngineType = TypeVar("EngineType", bound=type[SimulationEngine])
DomainType = TypeVar("DomainType", bound=type[DomainPlugin])
InterventionType = TypeVar("InterventionType", bound=type[PolicyIntervention])
PressureType = TypeVar("PressureType", bound=type[PressureScenario])

ENGINE_REGISTRY: dict[str, type[SimulationEngine]] = {}
DOMAIN_REGISTRY: dict[str, type[DomainPlugin]] = {}
INTERVENTION_REGISTRY: dict[str, type[PolicyIntervention]] = {}
PRESSURE_REGISTRY: dict[str, type[PressureScenario]] = {}


def _validate_registration_name(name: str, component: str) -> None:
    """Reject private or empty plugin names."""

    if not name or name.startswith("_"):
        raise ValueError(f"{component} registration name must be public and non-empty.")


def register_engine(name: str) -> Callable[[EngineType], EngineType]:
    """Register a simulation engine class under a unique name."""

    _validate_registration_name(name, "Engine")

    def decorator(cls: EngineType) -> EngineType:
        if name in ENGINE_REGISTRY:
            raise ValueError(f"Simulation engine '{name}' is already registered.")
        ENGINE_REGISTRY[name] = cls
        return cls

    return decorator


def register_domain(name: str) -> Callable[[DomainType], DomainType]:
    """Register a policy domain class under a unique name."""

    _validate_registration_name(name, "Domain")

    def decorator(cls: DomainType) -> DomainType:
        if name in DOMAIN_REGISTRY:
            raise ValueError(f"Policy domain '{name}' is already registered.")
        DOMAIN_REGISTRY[name] = cls
        return cls

    return decorator


def register_intervention(name: str) -> Callable[[InterventionType], InterventionType]:
    """Register a policy intervention class under a unique name."""

    _validate_registration_name(name, "Intervention")

    def decorator(cls: InterventionType) -> InterventionType:
        if name in INTERVENTION_REGISTRY:
            raise ValueError(f"Policy intervention '{name}' is already registered.")
        INTERVENTION_REGISTRY[name] = cls
        return cls

    return decorator


def register_pressure(name: str) -> Callable[[PressureType], PressureType]:
    """Register an exogenous pressure class under a unique name."""

    _validate_registration_name(name, "Pressure")

    def decorator(cls: PressureType) -> PressureType:
        if name in PRESSURE_REGISTRY:
            raise ValueError(f"Pressure scenario '{name}' is already registered.")
        PRESSURE_REGISTRY[name] = cls
        return cls

    return decorator


def SimulationEngineFactory(engine_name: str, cfg: Mapping[str, Any]) -> SimulationEngine:
    """Create a configured simulation engine by registered name."""

    engine_cls = ENGINE_REGISTRY.get(engine_name)
    if engine_cls is None:
        available = ", ".join(sorted(ENGINE_REGISTRY)) or "<none>"
        raise ValueError(
            f"Unknown simulation engine '{engine_name}'. Available engines: {available}"
        )
    return engine_cls(cfg)


def DomainPluginFactory(domain_name: str, cfg: Mapping[str, Any]) -> DomainPlugin:
    """Create a configured policy domain by registered name."""

    domain_cls = DOMAIN_REGISTRY.get(domain_name)
    if domain_cls is None:
        available = ", ".join(sorted(DOMAIN_REGISTRY)) or "<none>"
        raise ValueError(f"Unknown policy domain '{domain_name}'. Available domains: {available}")
    return domain_cls(cfg)


def PolicyInterventionFactory(
    intervention_name: str,
    cfg: Mapping[str, Any],
) -> PolicyIntervention:
    """Create a configured policy intervention by registered name."""

    intervention_cls = INTERVENTION_REGISTRY.get(intervention_name)
    if intervention_cls is None:
        available = ", ".join(sorted(INTERVENTION_REGISTRY)) or "<none>"
        raise ValueError(
            f"Unknown policy intervention '{intervention_name}'. Available: {available}"
        )
    return intervention_cls(cfg)


def PressureScenarioFactory(
    pressure_name: str,
    cfg: Mapping[str, Any],
) -> PressureScenario:
    """Create a configured pressure scenario by registered name."""

    pressure_cls = PRESSURE_REGISTRY.get(pressure_name)
    if pressure_cls is None:
        available = ", ".join(sorted(PRESSURE_REGISTRY)) or "<none>"
        raise ValueError(f"Unknown pressure scenario '{pressure_name}'. Available: {available}")
    return pressure_cls(cfg)


def available_engines() -> tuple[str, ...]:
    """Return registered engine names in stable order."""

    return tuple(sorted(ENGINE_REGISTRY))


def available_domains() -> tuple[str, ...]:
    """Return registered domain names in stable order."""

    return tuple(sorted(DOMAIN_REGISTRY))


def available_interventions() -> tuple[str, ...]:
    """Return registered intervention names in stable order."""

    return tuple(sorted(INTERVENTION_REGISTRY))


def available_pressures() -> tuple[str, ...]:
    """Return registered pressure names in stable order."""

    return tuple(sorted(PRESSURE_REGISTRY))


def import_modules(package_paths: Iterable[str], package_name: str) -> tuple[ModuleType, ...]:
    """Import public modules in a package so decorators can register plugins."""

    imported: list[ModuleType] = []
    for module_info in pkgutil.iter_modules(package_paths):
        if module_info.name.startswith("_"):
            continue
        imported.append(importlib.import_module(f"{package_name}.{module_info.name}"))
    return tuple(imported)
