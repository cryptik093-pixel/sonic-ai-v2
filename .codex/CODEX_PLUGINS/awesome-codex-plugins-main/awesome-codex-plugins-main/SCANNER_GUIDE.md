# Plugin Quality Guide

If you received a scanner report on your repo, here's how to use the [codex-plugin-scanner](https://github.com/hashgraph-online/codex-plugin-scanner) to check your progress and fix issues.

## Quick Start

```bash
# Install
pip install codex-plugin-scanner

# Run against your plugin
codex-plugin-scanner lint .

# Verbose output with explanations
codex-plugin-scanner lint . --format text
```

## GitHub Actions CI

Add a quality gate to your CI so every PR is checked automatically:

```yaml
- name: Codex plugin quality gate
  uses: hashgraph-online/hol-codex-plugin-scanner-action@v1
  with:
    plugin_dir: "."
    fail_on_severity: high
```

## Scoring

The scanner scores plugins 0-100 across these categories:

| Category | Max Points | What it checks |
|----------|-----------|----------------|
| Manifest Validation | 25 | Required fields, schema compliance |
| Security | 16 | Hardcoded secrets, secure defaults |
| Best Practices | 15 | SECURITY.md, LICENSE, Dependabot |
| Code Quality | 10 | Lockfiles, .codexignore |

## Common Fixes

### Missing SECURITY.md

Create `SECURITY.md` in your repo root with a vulnerability disclosure policy:

```markdown
# Security

To report a security vulnerability, please open an issue with the `[security]` label.
```

### Unpinned GitHub Actions

Replace floating tags with pinned commit SHAs:

```yaml
# Before
- uses: actions/checkout@v4

# After
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

### Missing LICENSE

Add a LICENSE file. MIT or Apache-2.0 are standard choices for plugin repos.

### Missing dependency lockfile

If you have `package.json`, add `package-lock.json`. If you have `requirements.txt`, add `requirements-lock.txt` or use `pip freeze > requirements-lock.txt`.

## Required Manifest Fields

The minimum `.codex-plugin/plugin.json` must include:

- `name` - Plugin display name
- `version` - Semantic version
- `description` - Short description
- `author` - Author info with at least `name`
- `skills` - Path to skills directory

## Getting Listed

If your plugin scores 60+ and has no critical or high findings, it's eligible for [awesome-codex-plugins](https://github.com/hashgraph-online/awesome-codex-plugins). Submit a PR following the [CONTRIBUTING.md](CONTRIBUTING.md) guide.

## More Info

- Scanner repo: [hashgraph-online/codex-plugin-scanner](https://github.com/hashgraph-online/codex-plugin-scanner)
- Full schema docs: [schemas/](https://github.com/hashgraph-online/codex-plugin-scanner/tree/main/schemas)
- HOL Plugin Registry: [hol.org/registry/plugins](https://hol.org/registry/plugins)
