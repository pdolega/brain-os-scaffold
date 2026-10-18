# Log

Append-only provenance record. Newest entries at the bottom.
**Never rewrite or delete an existing entry.**

Format: `- [YYYY-MM-DD] <operation> | <subject> | <detail>`, one list item per entry.
Canonical operations from AGENTS.md rule 9: `sync`, `triage`, `radar`, `promote`,
`retire`, `ingest`, `activity`, `query`, `review`, `feedback`, `lint`, `audit`,
`schema`, `correction`, `capture`, `maintenance`, `draft`, `agenda`, `human-instruction`.
The header may be updated; entries never.

