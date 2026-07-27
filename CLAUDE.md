# CLAUDE.md

Guidance for Claude agents working in this repository.

## Post-change review workflow

After any code change is complete (before considering the task done), review the
change in three separate passes. Do not combine these into a single pass — each is
dedicated to one concern so it gets full attention:

1. **Correctness pass.** Re-read the diff and ask: does this actually do what it's
   supposed to do? Check logic, edge cases, error handling, and that tests (if any)
   genuinely exercise the change rather than just asserting it didn't crash.
2. **Architecture pass.** Re-read the diff again, this time for structure: does it fit
   the existing patterns in the codebase, is it in the right place, is there
   unnecessary duplication or an abstraction that should be reused instead, is
   anything over- or under-engineered for what was asked.
3. **Security pass.** Re-read the diff a third time specifically for security issues:
   injection (SQL, command, prompt), unsanitized input crossing a trust boundary,
   secrets or credentials handled unsafely, path traversal, and similar OWASP-style
   concerns.

Each pass should be a distinct read-through of the change with that pass's question in
mind — not a single review that tries to think about all three at once.

## Desiderism — the ethical framework this application embodies

Desiderist is meant to uphold **Desiderism**, an ethical framework centered on
respecting people's genuine desires rather than imposing external standards on them or
letting anyone act without constraint. (Source: "An Introduction to Desiderism",
internal design doc.) This isn't background trivia — it should shape concrete design
and implementation decisions:

- **Desires ≠ urges ≠ wants.** The framework distinguishes subconscious *urges*,
  momentary *wants*, and genuine *desires* — a preferred complete world-state that
  accounts for long-term consequences and trade-offs, not a passing impulse. The
  desire-extraction step (`desires/extraction.py`) should keep holding this line: only
  record something as a tracked desire when the user's message actually supports it,
  not from speculation, hypotheticals, or passing mentions. Don't loosen this to
  capture every offhand remark as a "desire."
- **The guiding question is "what do I allow others to do to me?", not "what can I
  do?"** When designing any feature that has the harness act on a user's behalf,
  default to what the user has actually consented to / expressed, not what the harness
  judges best for them.
- **Guardianship is narrow.** Overriding a user's expressed wishes is only legitimate
  when they demonstrably lack the capacity to make decisions aligned with their own
  desired outcomes (the framework's examples: children, people impaired by addiction).
  The harness should not default to paternalism — don't build features that override,
  filter, or "protect the user from themselves" absent a real capacity concern.
- **Socially Agreed Acceptable Harms — the model for future multi-user conflict
  resolution.** The long-term goal (see project memory) is fulfilling one user's
  desires without harming others'. Desiderism's answer isn't "cause zero harm to
  anyone" (acknowledged as impossible — most actions cause some harm to someone) — it's
  a negotiated, consent-based acceptance of trade-offs between parties. When the
  multi-user milestone is designed, model conflict resolution as negotiation/agreement
  between desires, not as a hard-coded harm-avoidance rule.
- **Self-defense is bounded.** Ending an unjustifiable harm against oneself is morally
  excusable, but proportionally limited — not a blank check. If the harness ever needs
  logic for a user protecting their own interests against another party, keep any
  override power proportional to the harm being stopped.
- **Practical posture:** listen actively rather than assume (extraction should reflect
  what was actually said, not inferred intent); expect desires to change over time and
  update accordingly (the append-only desire event log with `update`/`contradict`
  already supports this — keep it that way); prefer incremental changes over drastic
  unilateral action; when multiple desires compete, weigh who is most in need; and be
  transparent about harms/trade-offs a justified action still causes rather than
  presenting actions as costless (e.g. action results and messages to the user should
  own the trade-off, not hide it).
