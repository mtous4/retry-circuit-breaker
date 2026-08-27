---
trigger: always_on
---

PROJECT 3 — AGENT RULES

IMPORTANT — READ THIS FIRST

1. SOURCE OF TRUTH — BRIEF
- The provided Project 3 BRIEF is the primary and permanent source of truth for this project.
- Always refer back to the BRIEF before making any project decision.
- Do not rely on memory or assumptions when the BRIEF can answer something.
- If the BRIEF specifies a requirement, follow it exactly.
- If the BRIEF does not specify something, do not present an invented rule as an instructor requirement.
- Assignment-level ambiguity must be reported to me so I can decide whether we need to ask the instructor.
- Policy-level ambiguity is part of the project: we are expected to make and document our own policy decision.

2. ABSOLUTELY NO GIT COMMITS
- NEVER create a Git commit.
- NEVER run `git commit`.
- NEVER run `git add` for the purpose of committing.
- NEVER push to a remote repository.
- NEVER create or amend commits.
- I will handle ALL Git commits manually myself.
- You may inspect Git status/history if needed, but you must not modify Git history.
- After completing a phase, only tell me what changed. Do not commit anything.

3. ALWAYS FOLLOW THE BRIEF
- Before starting each phase, read/re-check the @BRIEF (2).md .
- Treat the @BRIEF (2).md as the permanent source of truth throughout the entire project.
- If another file conflicts with the @BRIEF (2).md, stop and report the conflict.
- Do not silently resolve conflicts.
- Do not replace @BRIEF (2).md requirements with general best practices.

4. WORK PHASE BY PHASE
- Only work on the phase I explicitly ask you to work on.
- Do not automatically continue to the next phase.
- Do not implement anything early.
- Do not create tests before the testing phase.
- Do not implement production code before POLICY.md is complete.
- Wait for my instruction before moving to the next phase.

5. POLICY OWNERSHIP
- Project 3 does not provide a predefined retry/circuit-breaker policy.
- We decide the policy ourselves.
- Every policy decision must be documented in POLICY.md.
- Every decision must explain why we chose it.
- Clearly distinguish:
  - BRIEF requirement
  - Our decision
  - Assumption
- Never claim that the instructor required a policy decision that we made ourselves.