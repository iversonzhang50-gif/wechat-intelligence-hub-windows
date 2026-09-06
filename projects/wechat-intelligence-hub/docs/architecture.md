# Architecture

WeChat Intelligence Hub uses four deliberately separate layers:

1. **Reader**: `wechat-cli` or a compatible read-only adapter reads local WeChat data.
2. **Index**: SQLite, FTS, message hashes and run metadata preserve searchable evidence.
3. **Intelligence**: group threads, contact state, signals, candidates and opportunities turn evidence into local decisions.
4. **Interface**: Codex direct answers, Markdown and optional HTML expose the same local state without writing to WeChat. Targeted questions default to direct answers; HTML is generated from the final semantic Markdown only when interactive reading is useful.

The reader is replaceable. The intelligence database remains useful when live reading is temporarily unavailable. A failed live read must be reported as a coverage gap, never as proof that no message exists.

## Personalization Overlay

Personalization belongs to the intelligence layer, not the reader. `wechat-cli` remains a neutral read-only adapter; WeChat Intelligence Hub applies a local Profile containing the user's current work, personal context, focus topics and selected WeChat labels.

- Personal and planning documents stay local and are stored as source paths, not copied into the public release.
- Focus areas and custom topics change group relevance, topic summaries and private-chat prioritization.
- WeChat labels narrow recurring scans to relationship sets the user cares about, while full-database keyword search remains available.
- Public defaults do not assume any particular occupation or label names. A first-run profile without context remains `needs_context` and produces a preparation checklist instead of pretending to be personalized.

## Commercial Lifecycle

- `signal`: a message or repeated link that may be commercially relevant.
- `candidate`: an unreviewed cluster of signals. Candidates expire after 14 days without reinforcement by default.
- `opportunity`: a candidate promoted by clear direct evidence or human triage.
- `stale`: an unreviewed candidate whose evidence is no longer timely. Evidence is retained.
- `archived`: an intentionally closed record kept for history.

`triage pursue/wait/won` promotes the exact candidate and stores a confirmation feedback record. `ignore` stores an exact suppression so the same campaign does not immediately return.

## Read-Only Boundary

The project may update its own SQLite database, reports, feedback and local configuration. It must not send messages, click WeChat controls, add contacts or initiate payments.
