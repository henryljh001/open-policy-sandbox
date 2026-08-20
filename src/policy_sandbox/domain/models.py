"""Framework-neutral domain objects."""

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class EngineDescriptor:
    """Public identity of a simulation engine plugin."""

    name: str
    version: str


@dataclass(frozen=True)
class DomainDescriptor:
    """Public identity and compatibility envelope of a policy domain."""

    name: str
    version: str
    title: str
    status: str
    supported_scales: tuple[str, ...]
    supported_time_steps: tuple[str, ...]


@dataclass(frozen=True)
class InterventionDescriptor:
    """Public identity of a policy intervention plugin."""

    name: str
    version: str
    domain: str
    title: str


@dataclass(frozen=True)
class PressureDescriptor:
    """Public identity of an exogenous pressure-scenario plugin."""

    name: str
    version: str
    domain: str
    title: str


@dataclass(frozen=True)
class PolicyEffect:
    """Synthetic, auditable parameter changes emitted by one intervention."""

    rate_deltas: Mapping[str, float] = field(default_factory=dict)
    tracked_adjustments: Mapping[str, float] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PressureEffect:
    """Explicit synthetic rate and behavior changes emitted by a pressure."""

    rate_deltas: Mapping[str, float] = field(default_factory=dict)
    behavior_deltas: Mapping[str, float] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SimulationResult:
    """Minimal result returned by a simulation engine."""

    outcomes: Mapping[str, float]
    group_outcomes: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    warnings: tuple[Mapping[str, str], ...] = field(default_factory=tuple)
