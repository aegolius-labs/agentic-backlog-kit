# Sprint contract

Default sprint-eligible types are Story, Bug, and Task. Initiative, Epic, and Feature remain tracking layers and do not consume sprint capacity.

An item is selectable when:

- maturity is `ready`;
- status is neither Done nor Blocked;
- every dependency is already Done or selected earlier in the same plan;
- its Effort fits remaining capacity.

The algorithm walks the dependency-valid priority order once. A prerequisite that cannot fit is skipped, and its dependent remains ineligible. This is deliberately deterministic rather than an optimizer that changes choices between runs.

Committing a plan means updating only selected items with the exact GitHub iteration title and `status: Planned`, validating the manifest, then using a reviewed sync plan. Sprint planning itself never mutates GitHub.

