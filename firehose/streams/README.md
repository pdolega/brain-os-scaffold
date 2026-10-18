# Firehose streams

**Human-owned.** One page per broad monitoring lens (`<name>-stream.md`), e.g.
technology, climate, entrepreneurship. Streams decide what triage notices; they are
not goals. List each active stream under `firehose.active_streams` in
`config/source-policy.yml`.

Copy this into `firehose/streams/<name>-stream.md` to add one:

```markdown
---
type: firehose-stream
stream: <name>
domain: research
status: active
sensitivity: open
aliases: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <Name>

## Scope
- TODO: what this stream should catch.

## Exclusions
- TODO: what to drop even when it matches.

## Distinctions to preserve
- e.g. announcement vs. deployment vs. measured result; vendor claim vs. customer evidence.

## Likely durable destinations
- TODO: ventures, topics or initiatives this stream tends to feed.
```

Template and rules: `AGENTS.md` §4.16.
