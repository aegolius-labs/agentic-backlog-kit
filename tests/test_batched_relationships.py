"""S-R28-1: relationships are read in batches, so cost grows with pages, not issues."""

from __future__ import annotations

import math
import unittest

from agentic_backlog_kit.github import GitHubApiError
from agentic_backlog_kit.importing import build_import_plan
from agentic_backlog_kit.snapshot import RELATIONSHIP_BATCH_SIZE, GitHubSnapshotReader

from tests.helpers import is_relationship_query, item, manifest, relationship_data


ISSUES_PATH = "/repos/aegolius-labs/example/issues?state=all&per_page=100&page={page}"
EMPTY_PROJECT = {
    "organization": {
        "projectV2": {
            "items": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}
        }
    }
}


def _issue(number: int, *, item_id: str | None = None, repository: str | None = None) -> dict:
    issue = {
        "id": 1000 + number,
        "node_id": f"NODE_{number}",
        "number": number,
        "html_url": f"issue-{number}",
        "title": f"Issue {number}",
        "body": f"<!-- agentic-backlog-kit:id={item_id};schema=1 -->" if item_id else "",
        "state": "open",
        "type": {"name": "Task"},
        "labels": [],
    }
    if repository:
        issue["repository"] = {"nameWithOwner": repository}
    return issue


class CountingTransport:
    """Answer listing, Project and relationship reads, and count every call."""

    def __init__(self, issues: list[dict], relationships: dict | None = None) -> None:
        self.issues = issues
        self.relationships = relationships or {}
        self.rest_calls: list[tuple[str, str]] = []
        self.relationship_queries: list[str] = []
        self.blocked_by_pages: dict[int, list[list[dict]]] = {}
        self.follow_up_calls: list[dict] = []

    def rest(self, method: str, path: str, payload=None):
        self.rest_calls.append((method, path))
        for page in range(1, 1000):
            if path == ISSUES_PATH.format(page=page):
                return self.issues[(page - 1) * 100 : page * 100]
        raise AssertionError(f"unexpected REST call: {method} {path}")

    def graphql(self, query: str, variables: dict):
        if is_relationship_query(query):
            self.relationship_queries.append(query)
            data = relationship_data(query, self.relationships)
            for alias, node in data["repository"].items():
                pages = self.blocked_by_pages.get(int(alias[1:]))
                if pages:
                    node["blockedBy"] = {
                        "nodes": pages[0],
                        "pageInfo": {"hasNextPage": True, "endCursor": "page-1"},
                    }
            return data
        if "query BlockedBy" in query:
            self.follow_up_calls.append(variables)
            pages = self.blocked_by_pages[variables["number"]]
            index = int(variables["cursor"].split("-")[1])
            more = index + 1 < len(pages)
            return {
                "repository": {
                    "issue": {
                        "blockedBy": {
                            "nodes": pages[index],
                            "pageInfo": {
                                "hasNextPage": more,
                                "endCursor": f"page-{index + 1}" if more else None,
                            },
                        }
                    }
                }
            }
        if "query ProjectItems" in query:
            return EMPTY_PROJECT
        raise AssertionError("unexpected GraphQL query")


def _reader(transport) -> GitHubSnapshotReader:
    return GitHubSnapshotReader(
        transport, owner="aegolius-labs", repository="example", project_number=1
    )


class BatchedRelationshipTests(unittest.TestCase):
    def test_request_count_grows_with_batches_not_issues(self) -> None:
        count = 2 * RELATIONSHIP_BATCH_SIZE + 7
        issues = [_issue(number, item_id=f"T-{number}") for number in range(1, count + 1)]
        transport = CountingTransport(issues)

        snapshot = _reader(transport).read()

        self.assertEqual(count, len(snapshot["issues"]))
        self.assertEqual(
            math.ceil(count / RELATIONSHIP_BATCH_SIZE), len(transport.relationship_queries)
        )
        # A fixed ceiling, so shrinking the batch back towards one request per
        # issue fails here rather than moving the expectation with it.
        self.assertLessEqual(len(transport.relationship_queries), math.ceil(count / 25))
        relationship_rest = [
            path for _, path in transport.rest_calls if "/parent" in path or "blocked_by" in path
        ]
        self.assertEqual([], relationship_rest)

    def test_every_issue_is_asked_for_exactly_once(self) -> None:
        count = RELATIONSHIP_BATCH_SIZE + 3
        issues = [_issue(number, item_id=f"T-{number}") for number in range(1, count + 1)]
        transport = CountingTransport(issues)

        _reader(transport).read()

        asked = [
            alias
            for query in transport.relationship_queries
            for alias in relationship_data(query)["repository"]
        ]
        self.assertEqual(sorted(f"i{n}" for n in range(1, count + 1)), sorted(asked))

    def test_relationships_resolve_to_item_ids(self) -> None:
        base = _issue(1, item_id="T-BASE")
        value = _issue(2, item_id="T-VALUE")
        transport = CountingTransport([base, value], {2: (base, [base])})

        by_id = {issue["abk_id"]: issue for issue in _reader(transport).read()["issues"]}

        self.assertEqual("T-BASE", by_id["T-VALUE"]["parent_abk_id"])
        self.assertEqual(["T-BASE"], by_id["T-VALUE"]["depends_on_abk_ids"])
        self.assertIsNone(by_id["T-BASE"]["parent_abk_id"])

    def test_dependencies_past_the_first_hundred_are_paged_in(self) -> None:
        blockers = [_issue(number, item_id=f"T-{number}") for number in range(2, 252)]
        target = _issue(1, item_id="T-TARGET")
        transport = CountingTransport([target, *blockers])
        transport.blocked_by_pages = {1: [blockers[:100], blockers[100:200], blockers[200:]]}

        by_id = {issue["abk_id"]: issue for issue in _reader(transport).read()["issues"]}

        self.assertEqual(250, len(by_id["T-TARGET"]["depends_on_abk_ids"]))
        self.assertEqual(["page-1", "page-2"], [call["cursor"] for call in transport.follow_up_calls])

    def test_an_issue_github_cannot_find_fails_loudly(self) -> None:
        transport = CountingTransport([_issue(1, item_id="T-1")])
        original = transport.graphql

        def drop_issue(query, variables):
            data = original(query, variables)
            if is_relationship_query(query):
                data["repository"]["i1"] = None
            return data

        transport.graphql = drop_issue

        with self.assertRaisesRegex(GitHubApiError, "Issue #1 was not found"):
            _reader(transport).read()


class ForeignRepositoryTests(unittest.TestCase):
    """A relationship into another repository must never match a local number."""

    def test_a_foreign_marked_blocker_is_not_a_local_dependency(self) -> None:
        local = _issue(1, item_id="T-1")
        foreign = _issue(1, item_id="T-1", repository="aegolius-labs/other")
        transport = CountingTransport([local], {1: (foreign, [foreign])})

        read = _reader(transport).read()["issues"][0]

        self.assertIsNone(read["parent_abk_id"])
        self.assertEqual([], read["depends_on_abk_ids"])

    def test_a_same_repository_relationship_still_resolves(self) -> None:
        base = _issue(1, item_id="T-BASE", repository="aegolius-labs/example")
        value = _issue(2, item_id="T-VALUE")
        transport = CountingTransport([base, value], {2: (base, [base])})

        by_id = {issue["abk_id"]: issue for issue in _reader(transport).read()["issues"]}

        self.assertEqual("T-BASE", by_id["T-VALUE"]["parent_abk_id"])

    def test_adoption_withholds_a_blocker_that_lives_elsewhere(self) -> None:
        # The foreign blocker shares its number with a local issue being
        # adopted, so matching by number alone would link the wrong #5.
        adopted = _issue(7)
        local_five = _issue(5)
        foreign_five = _issue(5, repository="aegolius-labs/other")
        transport = CountingTransport([local_five, adopted], {7: (None, [foreign_five])})

        unmanaged = _reader(transport).read_unmanaged(with_relationships=True)
        observed = next(issue for issue in unmanaged if issue["number"] == 7)
        self.assertEqual(
            [{"number": 5, "abk_id": None, "repository": "aegolius-labs/other"}],
            observed["blocked_by"],
        )

        plan = build_import_plan(
            manifest(item("T-EXISTING")),
            unmanaged,
            infer_relationships=True,
        )

        proposed = {entry["id"]: entry for entry in plan.items}
        adopted_item = next(entry for entry in proposed.values() if entry["id"].endswith("7"))
        self.assertEqual([], adopted_item["depends_on"])
        self.assertIn(
            "blocked by: issue aegolius-labs/other#5 is in another repository",
            plan.withheld_relationships[adopted_item["id"]],
        )


if __name__ == "__main__":
    unittest.main()
