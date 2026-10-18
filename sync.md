# Sync watermarks

Cache of the newest item per source. **The filesystem is the truth; this file is
disposable.** Rebuild direct-evidence sources from `raw/`. For Readwise, build the
identity/exclusion set from the union of `firehose/**/readwise/` and
`raw/**/readwise/`, keyed by `source_id`; rebuild its `updated_at` watermark from
firehose items only, because raw snapshots do not carry that field. With no firehose
item, initialize it from the configured `start_from` boundary.
Maintained by the agent at every `/brain:sync`. The human never edits it.

History starts at `start_from` in `config/source-policy.yml`.

| Source | Last watermark | Last source_id | Last sync at | Written | Skipped | Note |
|---|---|---|---|---|---|---|
| plaud | — | — | — | — | — | not synced yet |
| readwise | — | — | — | — | — | not synced yet |
| youtube | — | — | — | — | — | on-request URLs only |
| web | — | — | — | — | — | on-request URLs only |
| notes | — | — | — | — | — | not synced yet |
| substack | — | — | — | — | — | disabled until configured |
| typefully | — | — | — | — | — | disabled until configured |
| linkedin | — | — | — | — | — | disabled until configured |
| attachments | — | — | — | — | — | not synced yet |
| email | — | — | — | — | — | disabled until configured |
| email-scan | — | — | — | — | — | per-account newest message time scanned by `/brain:mail` |

Timestamps in `captured` and `updated_at` are local time; connectors that return UTC
are converted on write.
