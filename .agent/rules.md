# .agent/rules.md — compatibility entry point

- **Status:** policy pointer; human review required for changes.
- **Owner:** D (D3).
- **Authoritative rules:** `AGENTS.md`, `.opencode/rules.md`,
  `docs/architecture/permission-model.md`,
  `docs/code-governance/mcp-tool-manifest.md`.

This file exists for executors that look for `.agent/rules.md`. It does **not** create a
second policy or override the authoritative files. If any of these files disagree, stop
and ask the human owner to resolve the conflict.

Human-only rules remain in `.opencode/rules.md`; agents may propose text but may not write
it. Runtime enforcement of `.agent/` or `.opencode/` is not claimed by this pointer. The
enforced evidence is the independent checkers and required CI checks, not the presence of
this Markdown file.
