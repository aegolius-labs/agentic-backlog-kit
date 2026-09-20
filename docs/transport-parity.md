# Transport parity and the dedicated-MCP decision (R13)

Native GitHub Projects access is a transport invariant, not an MCP-only
feature. A capability-complete host integration, an authenticated GitHub CLI,
and direct GraphQL/REST are peer execution routes over one deterministic
engine. This records what "peer" is enforced to mean, and the decision about
building a dedicated MCP server.

## The routes

| Route | Status | Notes |
| --- | --- | --- |
| `gh` — authenticated GitHub CLI | Supported, capability-complete | Token never enters this process |
| `api` — direct GraphQL/REST | Supported, capability-complete | A peer, **not** a fallback for hosts without `gh` |
| Generic GitHub MCP | Not supported | Evaluated in Wave C; no Projects surface |

`gh` and `api` are peers in the strict sense: the same plan, digest, apply,
receipt and verification contract, and the same observable behaviour for the
same request.

## Capability preflight

Peer status was previously a claim in a document with nothing checking it. A
route was selected and the apply simply began, so an incomplete route failed
partway through with writes already committed — the failure mode a fail-closed
design exists to prevent.

Now every action kind declares what it requires and every transport declares
what it provides:

| Capability | Actions requiring it |
| --- | --- |
| `issue.write` | `issue.create`, `issue.update`, `issue.adopt` |
| `issue.hierarchy` | `issue.set_parent` |
| `issue.dependency` | `issue.add_dependency` |
| `project.item.write` | `project.add_item`, `project.set_fields`, `project.transition` |
| `project.field.write` | `project.field.create`, `project.field.update_options` |
| `project.iteration.write` | `project.field.update_iterations` |
| `project.view.write` | `project.view.create`, `project.view.update` |
| `project.lifecycle` | `project.create`, `project.link_repository` |
| `repository.label.write` | `repository.label.create` |

Every apply — sync, scaffold, iteration, bootstrap and import — refuses before
its first write when the selected route cannot finish the plan:

```
Route 'generic-mcp' cannot complete this plan; it is missing
project.item.write. Select a capability-complete route rather than mixing
transports within one apply.
```

Inspect a route without planning anything:

```bash
abk capabilities --backend gh
```

A transport that declares no capabilities is assumed complete, so a caller
supplying its own transport is not silently treated as incapable.

## Parity is tested, not asserted

Both peer routes are driven through the same service in
`tests/test_transport_parity.py`, and the outcomes must agree. This is not
ceremony — parity had already broken twice, in ways only a comparison finds:

**An unavailable issue type diverged.** `gh api` exits 1 for every API failure
and leaves the real status in its stderr text. The `native_or_label` fallback
keys off a 422, so it could never fire on the CLI route: the same manifest
converged through `api` and died mid-apply through `gh`. Found by running the
kit on its own backlog, which stopped at action 31 of 169.

**Diagnostics diverged.** After the narrow fix above, a 403, 429 or 500 still
reported as exit code 1 on the CLI route, so the hints that explain a failure
(R22) fired on `api` and never on `gh`. Found by the parity test itself.

Both are fixed. The reported status is now taken as the status, with one
deliberate exception: a 404 is only mapped for the exact endpoint and message
pair meaning an issue has no parent, because `GET .../parent` also answers 404
when the issue itself is absent, and conflating those would turn a missing
issue into a silent success.

## Decision: no dedicated MCP server

**Decided 2026-09-19. Do not build one.** Three reasons, in order of weight.

### It would put the snapshot in the model's context

The kit's central design choice is that bulk GitHub state never reaches the
model. A snapshot is written to a file and the model sees a compact summary.
The measured artifacts:

| Backlog | Snapshot artifact | Cold sync plan |
| --- | ---: | ---: |
| 100 items | 75,240 bytes (~18,810 tokens) | 72,319 bytes (~18,080 tokens) |
| 1,000 items | 753,349 bytes (~188,338 tokens) | 720,417 bytes (~180,105 tokens) |
| 10,000 items | 7,552,509 bytes (~1,888,128 tokens) | 7,202,332 bytes (~1,800,583 tokens) |

An MCP tool returns its result to the model. Routing discovery through MCP
would move those artifacts into context and undo R09 entirely. Nothing about a
dedicated server changes that: it is a property of where MCP results go.

### The call volume belongs in a process, not a conversation

A cold sync of a representative backlog:

| Backlog | Write calls | Snapshot read calls |
| --- | ---: | ---: |
| 100 items | 222 | ~201 |
| 1,000 items | 2,220 | ~2,001 |

Two thousand tool invocations is not a conversation. The plan/apply engine
already runs them in a loop with journaling and fail-closed recovery, which is
the right shape for that volume.

### A third route is a third route to keep at parity

Parity between two routes broke twice in a single day of real use. Each added
transport multiplies the surface where a capability-complete claim can quietly
stop being true, and a dedicated server would add one whose failures are
hardest to observe. The roadmap's own constraint — that such a server must not
duplicate planning logic — means it would be a thin adapter over the same REST
and GraphQL calls the direct route already makes, so it buys no capability at
the cost of a parity obligation.

### What would change this

Revisit if any of these becomes true:

- A host GitHub integration ships a capability-complete Projects surface, in
  which case it is adopted as a third peer under the same preflight — no
  dedicated server is needed for that.
- MCP gains a way to return a result to the caller without placing it in model
  context, which would remove the first reason entirely.
- A user needs the kit driven from a host that can reach MCP but cannot run a
  local process, which is the one gap a dedicated server genuinely closes.

Until then, `gh` and direct GraphQL/REST are the supported routes, and this
repository deliberately ships no `.mcp.json`: declaring a route the kit's own
evidence says cannot complete an apply would advertise a capability that does
not exist.
