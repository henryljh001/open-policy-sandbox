"""Tests for repeated stochastic experiments and calibration interfaces."""

import unittest

from policy_sandbox.application import run_experiment
from policy_sandbox.domains.new_urbanization.microsim.calibration import (
    assess_calibration,
)
from policy_sandbox.domains.new_urbanization.microsim_scenario import (
    build_microsim_scenario,
)


class ExperimentRunnerTests(unittest.TestCase):
    """Verify reproducible intervals, failures, groups, and moment checks."""

    def test_hundred_repeat_extreme_pressure_reports_failures(self) -> None:
        scenario = build_microsim_scenario(
            "S6",
            pressures=("extreme_disruption",),
            sample_size=200,
        )
        first = run_experiment(scenario, repetitions=100)
        second = run_experiment(scenario, repetitions=100)
        self.assertEqual(first, second)
        self.assertEqual(first["successful_runs"] + first["failed_runs"], 100)
        self.assertGreater(first["failed_runs"], 0)
        self.assertLess(first["failed_runs"], 100)
        summary = first["outcome_summary"]["micro_employment_rate_pct"]
        self.assertLessEqual(summary["p05"], summary["p50"])
        self.assertLessEqual(summary["p50"], summary["p95"])
        self.assertIn("skill:low", first["group_summary"])

    def test_no_pressure_repetitions_all_succeed(self) -> None:
        scenario = build_microsim_scenario("S0", sample_size=200)
        result = run_experiment(scenario, repetitions=10, base_seed=100)
        self.assertEqual(result["successful_runs"], 10)
        self.assertEqual(result["failed_runs"], 0)
        self.assertEqual(result["failure_rate"], 0.0)

    def test_calibration_interface_reports_pass_and_fail(self) -> None:
        simulated = {"employment_rate_pct": 70.0, "service_access_rate_pct": 65.0}
        passing = assess_calibration(
            simulated,
            {
                "employment_rate_pct": {
                    "target": 72.0,
                    "tolerance": 3.0,
                    "mode": "absolute",
                },
                "service_access_rate_pct": {
                    "target": 64.0,
                    "tolerance": 0.05,
                    "mode": "relative",
                },
            },
        )
        failing = assess_calibration(
            simulated,
            {
                "employment_rate_pct": {
                    "target": 80.0,
                    "tolerance": 2.0,
                    "mode": "absolute",
                }
            },
        )
        self.assertTrue(passing["all_passed"])
        self.assertFalse(failing["all_passed"])


if __name__ == "__main__":
    unittest.main()
