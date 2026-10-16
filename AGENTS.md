# Agent contract — Codex / Claude Code / Gemini CLI

All three agents are interchangeable. Git history and these documents are the sole shared source of truth. Do not rely on chat memory.

## Mandatory session protocol
1. `git status --short`; read README, PROJECT_STATE, HANDOFF, SAFETY and RESEARCH_PLAN.
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
- Use separate branches per agent/task if parallel; never write concurrently to the same working tree.
- Prefer small, reviewable commits. Include a short evidence and confidence summary in each research commit.
- Before quota exhaustion, prioritize a complete HANDOFF.md over starting new work.
