"""S-R29-1: an issue the Project item list omits is asked for its own membership."""

from __future__ import annotations

import math
import unittest

from agentic_backlog_kit.snapshot import MEMBERSHIP_BATCH_SIZE, GitHubSnapshotReader

from tests.helpers import (
    is_membership_query,
    is_relationship_query,
    membership_data,
    relationship_data,
)


ISSUES_PATH = "/repos/aegolius-labs/example/issues?state=all&per_page=100&page={page}"


def _issue(number: int) -> dict:
    return {
        "id": 1000 + number,
        "node_id": f"NODE_{number}",
        "number": number,
        "html_url": f"issue-{number}",
        "title": f"Issue {number}",
        "body": f"<!-- agentic-backlog-kit:id=T-{number};schema=1 -->",
        "state": "open",
        "type": {"name": "Task"},
        "labels": [],
    }


def _status(value: str) -> dict:
    return {
        "fieldValues": {
            "nodes": [{"field": {"name": "Status"}, "name": value}]
        }
    }


def _listed(number: int, status: str) -> dict:
    return {
        "id": f"ITEM_{number}",
        "content": {
            "id": f"NODE_{number}",
            "number": number,
            "repository": {"nameWithOwner": "aegolius-labs/example"},
        },
        **_status(status),
    }


def _membership(
    number: int, status: str, *, project: int = 1, owner: str = "aegolius-labs"
) -> dict:
    return {
        "id": f"ITEM_{number}_P{project}_{owner}",
        "project": {"number": project, "owner": {"login": owner}},
        **_status(status),
    }


class LaggingProjectTransport:
    """A repository whose Project item list lags behind the issues' own view."""

    def __init__(self, issues: list[dict], listed: list[dict], memberships: dict) -> None:
        self.issues = issues
        self.listed = listed
        self.memberships = memberships
        self.membership_queries: list[list[str]] = []

    def rest(self, method: str, path: str, payload=None):
        for page in range(1, 1000):
            if path == ISSUES_PATH.format(page=page):
                return self.issues[(page - 1) * 100 : page * 100]
        raise AssertionError(f"unexpected REST call: {method} {path}")

    def graphql(self, query: str, variables: dict):
        if is_relationship_query(query):
            return relationship_data(query)
        if "query ProjectItems" in query:
            return {
                "organization": {
                    "projectV2": {
                        "items": {
                            "nodes": self.listed,
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        if is_membership_query(query):
            self.membership_queries.append(list(variables["ids"]))
            return membership_data(variables, self.memberships)
        raise AssertionError("unexpected GraphQL query")


def _read(transport: LaggingProjectTransport) -> dict[str, dict]:
    snapshot = GitHubSnapshotReader(
        transport, owner="aegolius-labs", repository="example", project_number=1
    ).read()
    return {issue["abk_id"]: issue for issue in snapshot["issues"]}


class ProjectMembershipFallbackTests(unittest.TestCase):
    def test_an_issue_missing_from_the_list_is_read_from_its_own_project_items(self) -> None:
        transport = LaggingProjectTransport(
            [_issue(1), _issue(2)],
            listed=[_listed(1, "Ready")],
            memberships={"NODE_2": [_membership(2, "In Progress")]},
        )

        issues = _read(transport)

        self.assertTrue(issues["T-2"]["in_project"])
        self.assertEqual("ITEM_2_P1_aegolius-labs", issues["T-2"]["project_item_id"])
        self.assertEqual({"Status": "In Progress"}, issues["T-2"]["project_fields"])
        self.assertEqual({"Status": "Ready"}, issues["T-1"]["project_fields"])
        # Only the issue the list left out is asked.
        self.assertEqual([["NODE_2"]], transport.membership_queries)

    def test_an_issue_absent_from_both_is_still_not_in_the_project(self) -> None:
        transport = LaggingProjectTransport([_issue(1)], listed=[], memberships={})

        issue = _read(transport)["T-1"]

        self.assertFalse(issue["in_project"])
        self.assertIsNone(issue["project_item_id"])
        self.assertEqual({}, issue["project_fields"])

    def test_membership_of_another_project_does_not_count(self) -> None:
        transport = LaggingProjectTransport(
            [_issue(1)],
            listed=[],
            memberships={
                "NODE_1": [
                    _membership(1, "Done", project=2),
                    _membership(1, "Done", owner="someone-else"),
                ]
            },
        )

        self.assertFalse(_read(transport)["T-1"]["in_project"])

    def test_the_configured_project_is_found_among_several(self) -> None:
        transport = LaggingProjectTransport(
            [_issue(1)],
            listed=[],
            memberships={
                "NODE_1": [
                    _membership(1, "Done", project=2),
                    _membership(1, "Ready", owner="AEGOLIUS-LABS"),
                ]
            },
        )

        issue = _read(transport)["T-1"]

        self.assertTrue(issue["in_project"])
        self.assertEqual({"Status": "Ready"}, issue["project_fields"])

    def test_the_fallback_is_batched_not_one_call_per_missing_issue(self) -> None:
        count = 2 * MEMBERSHIP_BATCH_SIZE + 7
        issues = [_issue(number) for number in range(1, count + 1)]
        listed = [_listed(number, "Ready") for number in range(1, 11)]
        transport = LaggingProjectTransport(issues, listed=listed, memberships={})

        _read(transport)

        missing = count - len(listed)
        self.assertEqual(
            math.ceil(missing / MEMBERSHIP_BATCH_SIZE), len(transport.membership_queries)
        )
        asked = [node for batch in transport.membership_queries for node in batch]
        self.assertEqual(missing, len(asked))
        self.assertEqual(len(asked), len(set(asked)))

    def test_a_converged_project_costs_no_extra_request(self) -> None:
        transport = LaggingProjectTransport(
            [_issue(1), _issue(2)],
            listed=[_listed(1, "Ready"), _listed(2, "Ready")],
            memberships={},
        )

        _read(transport)

        self.assertEqual([], transport.membership_queries)


if __name__ == "__main__":
    unittest.main()
