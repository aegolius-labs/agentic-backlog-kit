# Source extraction boundary

Discovery reviewed `aegolius-labs/aio-agentic-sdlc` at commit `1a24da707d6866b7b1bc9d11d2cf87c924bc1dfa`.

Concepts adapted:

- deterministic Impact/Effort scoring;
- dependency cycle detection and topological ordering;
- prerequisite score boosting;
- hierarchy validation;
- compact local machine-readable state;
- CLI and agent-skill separation;
- test-first coverage of safety invariants.

Changes made for this project:

- GitHub Issues and Projects replace local backlog state as the operational authority;
- Business Value and Enabler Value extend the scoring matrix;
- local state is a compact declarative manifest, not an execution queue;
- all external mutations use digest-bound plan/apply workflows;
- native sub-issues, issue dependencies, iteration fields, and Project views are first-class targets;
- runtime code is an independent standard-library implementation.

The dual Intention/Reality DAG system, semantic reconciliation, source-code traceability, SDLC orchestration roles, document generation, and bundled MCP server were deliberately excluded.

The reviewed source declares the PolyForm Noncommercial License 1.0.0. No source files were copied into this repository. A license for this independently written project remains an explicit owner decision.

