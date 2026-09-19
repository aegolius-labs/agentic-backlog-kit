from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import (
    CYCLE_DIAGNOSTIC_LIMIT,
    ManifestError,
    validate_manifest,
)
from agentic_backlog_kit.priority import prioritize

from tests.helpers import item, manifest


def _identifier(index: int) -> str:
    return f"T-{index:05d}"


def _chain(length: int, *, reverse: bool = False) -> dict:
    """Build one linear dependency chain of the requested length.

    A forward chain depends backwards through sorted ids; a reverse chain
    depends forwards, which is the order that drives a sorted depth-first walk
    to its deepest point.
    """

    items = []
    for index in range(length):
        if reverse:
            depends_on = [_identifier(index + 1)] if index < length - 1 else []
        else:
            depends_on = [_identifier(index - 1)] if index else []
        items.append(item(_identifier(index), depends_on=depends_on))
    return manifest(*items)


class DeepDependencyGraphTests(unittest.TestCase):
    """R17 - deep graphs must resolve iteratively instead of exhausting the stack."""

    def test_validates_a_deep_forward_chain(self) -> None:
        normalized = validate_manifest(_chain(10_000))

        self.assertEqual(10_000, len(normalized["items"]))

    def test_validates_a_deep_reverse_chain(self) -> None:
        normalized = validate_manifest(_chain(10_000, reverse=True))

        self.assertEqual(10_000, len(normalized["items"]))

    def test_prioritizes_a_deep_chain_in_dependency_order(self) -> None:
        scored = prioritize(_chain(10_000))

        self.assertEqual(10_000, len(scored))
        self.assertEqual(_identifier(0), scored[0].id)
        self.assertEqual(_identifier(9_999), scored[-1].id)

    def test_detects_a_deep_cycle_without_recursion_failure(self) -> None:
        length = 5_000
        items = [
            item(_identifier(index), depends_on=[_identifier((index + 1) % length)])
            for index in range(length)
        ]

        with self.assertRaisesRegex(ManifestError, "Dependency cycle detected"):
            validate_manifest(manifest(*items))

    def test_bounds_the_cycle_diagnostic_for_a_long_cycle(self) -> None:
        length = 5_000
        items = [
            item(_identifier(index), depends_on=[_identifier((index + 1) % length)])
            for index in range(length)
        ]

        with self.assertRaises(ManifestError) as raised:
            validate_manifest(manifest(*items))

        message = str(raised.exception)
        # The reported path repeats the entry node, so it holds length + 1 ids.
        omitted = length + 1 - CYCLE_DIAGNOSTIC_LIMIT
        self.assertIn(f"... {omitted} more ...", message)
        self.assertLess(len(message), 512)

    def test_reports_a_short_cycle_in_full(self) -> None:
        data = manifest(
            item("T-1", depends_on=["T-2"]),
            item("T-2", depends_on=["T-3"]),
            item("T-3", depends_on=["T-1"]),
        )

        with self.assertRaisesRegex(ManifestError, r"T-1 -> T-2 -> T-3 -> T-1"):
            validate_manifest(data)


class CompletedWorkScoringTests(unittest.TestCase):
    """R18 - completed work scores zero and never propagates a dependency boost."""

    def test_completed_work_scores_zero_despite_dependents(self) -> None:
        data = manifest(
            item("T-DONE", status="Done"),
            item("T-A", depends_on=["T-DONE"], impact=5, business_value=5),
            item("T-B", depends_on=["T-DONE"], impact=5, business_value=5),
        )

        scores = {scored.id: scored.priority_score for scored in prioritize(data)}

        self.assertEqual(0.0, scores["T-DONE"])

    def test_completed_work_does_not_relay_a_boost_to_its_prerequisite(self) -> None:
        data = manifest(
            item("T-ROOT"),
            item("T-DONE", depends_on=["T-ROOT"], status="Done"),
            item("T-LATER", depends_on=["T-DONE"], impact=5, business_value=5),
        )

        scores = {scored.id: scored.priority_score for scored in prioritize(data)}

        # T-ROOT keeps its own base score only; the finished T-DONE relays nothing.
        self.assertEqual(scores["T-ROOT"], prioritize(data)[0].base_score)
        self.assertEqual(0.0, scores["T-DONE"])

    def test_unfinished_prerequisites_still_receive_a_boost(self) -> None:
        data = manifest(
            item("T-ROOT"),
            item("T-OPEN", depends_on=["T-ROOT"], impact=5, business_value=5),
        )

        scored = {entry.id: entry for entry in prioritize(data)}

        self.assertGreater(
            scored["T-ROOT"].priority_score, scored["T-ROOT"].base_score
        )

    def test_honours_custom_done_statuses(self) -> None:
        data = manifest(
            item("T-SHIPPED", status="Released"),
            item("T-NEXT", depends_on=["T-SHIPPED"], impact=5, business_value=5),
        )
        data["workflow"]["statuses"].append("Released")
        data["workflow"]["done_statuses"] = ["Done", "Released"]

        scores = {scored.id: scored.priority_score for scored in prioritize(data)}

        self.assertEqual(0.0, scores["T-SHIPPED"])
