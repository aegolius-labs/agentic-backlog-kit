# Security policy

## Supported versions

Security fixes are provided for the latest released minor version. Before `1.0.0`, support is best effort and may require upgrading to the newest release.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for the `aegolius-labs/agentic-backlog-kit` repository once it is published. If private reporting is unavailable, contact Aegolius Labs through the organization page at https://github.com/aegolius-labs and request a private reporting channel.

Do not disclose suspected vulnerabilities in a public issue. Include affected versions, reproduction steps, impact, and any suggested mitigation. Never include live GitHub tokens, credentials, or private backlog contents.

## Security boundaries

The kit can write GitHub Issues and organization Projects. External mutations require a reviewed plan digest and explicit confirmation. Use the least-privileged GitHub token or MCP connection that provides organization Projects write access, repository Issues write access for issue reconciliation, and repository Contents access when creating or linking a Project.

The release is intentionally additive and update-only: it does not delete
issues, remove relationships, archive Project items, or automatically close
issues. A post-apply Project refresh may temporarily lag membership writes; the
safe response is to refresh and re-plan after propagation rather than replaying
an earlier digest. See the [release-candidate limitations](README.md#release-candidate-support-and-limitations)
for the transport and Project-view boundaries.
