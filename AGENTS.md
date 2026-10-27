# Agent contract — Codex / Claude Code / Gemini CLI

All three agents are interchangeable. Git history and these documents in `/Users/avp/project/g3x-lite` (tracking `origin` at `https://github.com/s4urj3ng/g3x-lite`) are the sole shared source of truth. Do not rely on chat memory.

- **Canonical repository (ONLY active workspace)**: `/Users/avp/project/g3x-lite`
- **GitHub remote (`origin`)**: `https://github.com/s4urj3ng/g3x-lite`
- **Retired backup (DO NOT USE for work)**: `/Users/avp/Downloads/g3x-lite`

## Mandatory session protocol
1. Verify working directory is `/Users/avp/project/g3x-lite`; run `git status --short`; read README, PROJECT_STATE, HANDOFF, SAFETY and RESEARCH_PLAN.
2. State the task, existing evidence, unknowns and intended files before work.
3. Research one bounded question at a time. Distinguish verified / plausible / unknown / contradicted.
4. Record each finding with exact URL, retrieval date, revision/commit when applicable, and what the source actually proves.
5. Commit only documentation/scripts approved for Phase 0. Never commit proprietary firmware, credentials or Ghidra projects.
6. Update PROJECT_STATE and HANDOFF with exact next command, blockers and evidence. Leave the worktree clean or explain why.

## Scope restrictions
- Phase 0 is READ ONLY regarding firmware and camera hardware.
- No REA, Ghidra or MCP setup yet. No firmware flashing, camera connection, binary modification, boot scripts or execution.
- Do not infer firmware addresses, CPU mode, offsets or exploitability without evidence.
- Do not run unreviewed downloaded scripts. Never bypass safeguards to test on physical camera.
- Any phase transition requires explicit human approval.

## Coordination
- Work exclusively in `/Users/avp/project/g3x-lite` and keep `main` synchronized with `origin/main` via normal fast-forward pushes (never force-push).
- Use separate branches per agent/task if parallel; never write concurrently to the same working tree.
- Prefer small, reviewable commits. Include a short evidence and confidence summary in each research commit.
- Before quota exhaustion, prioritize a complete HANDOFF.md over starting new work.

## AgentBridge mode (owner-approved)

When a task is dispatched by AgentBridge (the prompt says so and the working directory is an
AgentBridge git worktree on the AgentBridge host):

- The workspace is that worktree, not `/Users/avp/project/g3x-lite`. Do not change directory
  elsewhere, push, rebase or touch `main`. AgentBridge commits, validates, integrates into
  `agentbridge/*` branches and opens draft PRs only after owner approval.
- Read README, docs/SAFETY.md, docs/PROJECT_STATE.md, docs/HANDOFF.md and docs/RESEARCH_PLAN.md
  as usual. All scope restrictions above still apply (Phase 0 read-only regarding firmware and
  hardware; STRICT NO-GO).
- Do not edit docs/PROJECT_STATE.md or docs/HANDOFF.md unless the task explicitly asks for it.
  The milestone's final task updates them once, which avoids merge conflicts between parallel tasks.
- Report findings in the task result with VERIFIED / INFERRED / UNKNOWN labels and exact citations.
  The evidence and commit rules above still apply.
- Never run tests/test_validate_witness_inspector.py or tools/build_witness_inspector.py: they
  build a camera payload binary.
