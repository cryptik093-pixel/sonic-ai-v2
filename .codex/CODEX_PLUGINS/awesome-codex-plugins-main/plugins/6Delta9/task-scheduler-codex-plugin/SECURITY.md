# Security Policy

## Supported Versions

Task Scheduler is currently maintained as a single active line on the `main` branch.

Security fixes, documentation fixes, and dependency updates are applied to the latest version in this repository.

## Reporting a Vulnerability

If you believe you have found a security issue in this plugin:

1. Do not open a public GitHub issue with exploit details.
2. Send a report to `opensource@6delta9.dev`.
3. Include:
   - a short description of the issue
   - affected files or components
   - reproduction steps
   - impact assessment if known

You can also open a GitHub issue for non-sensitive security hardening suggestions that do not expose a live vulnerability:

https://github.com/6Delta9/task-scheduler-codex-plugin/issues

## Scope

This repository is a local-first Codex plugin and MCP server starter. Security review is especially relevant for:

- shell execution paths
- file path handling
- MCP tool inputs
- third-party dependencies
- future hooks or app integrations

## Disclosure Expectations

- I will try to acknowledge reports promptly.
- Public disclosure should wait until the issue is understood and a fix or mitigation is available.
- If a report turns out to be low risk or non-exploitable, it may be handled as a regular improvement instead of a security advisory.
