---
type: context
domain: none
---

# Who I am, operationally

_Human-owned. The agent reads this at the start of every session, together with
`goals/goals.md`, and never edits it._

This is not a biography. Every line here exists because it changes the agent's
output. If a sentence would not change what it writes, delete it.

## Hats

TODO: the roles you play, one bullet each, and what each means for the agent.
For example: your day job (the richest evidence source, never a goal; the
promotion filter is `AGENTS.md` §5.1a); a founder exploring one or two business
hypotheses; a writer.

## Where I have real standing

TODO: the subjects you can make assertions about. Outside this list you can only
ask questions, and the agent flags any seed that asserts something outside it.

## Audiences

TODO: one bullet per reader segment, each starting with a backticked slug. Replace
the example below; lint ignores any line containing the word "example" or TODO.

- **`founders`** (example, default) — who they are and what they want from you.

These slugs are the only legal audience values on seeds and drafts
(`tools/lint.py` reads them from this section). With none listed, audience is
unchecked.

Per-channel register, same reader:

- TODO: e.g. X — short and specific; LinkedIn — the tradeoff in a few paragraphs;
  essays — an argued piece with evidence.

## Voice

How you sound lives in `voice.md`, next to this file.

## Standing constraints

- Never name a client, or attribute a quote to a named colleague, in anything
  outward-facing. Anonymize to a segment ("a mid-size utility", "a CTO I work with").
- Never publish anything derived from a recorded call without explicit approval,
  even anonymized.
- Restricted material may be quoted or cited only anonymized. You are the gate
  before anything leaves.
- TODO: anything else you never publish (family, health, finances, …) and your
  default language.

## Not interested in

Discard silently, do not surface:

- TODO: topics the agent should drop without mentioning them.

## Anti-goals

- TODO: kinds of work or projects you do not want to be pulled into.
