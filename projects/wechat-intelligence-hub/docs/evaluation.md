# Evaluation

Evaluate the system on anonymized, human-labeled windows instead of judging it by how many signals it produces.

## Weekly Metrics

- **Top-10 precision**: at least 8 of the first 10 candidates are worth reviewing.
- **Duplicate rate**: one brand/project/round should produce one candidate card.
- **Stale rate**: candidates without new evidence leave the active inbox automatically.
- **Missed-opportunity recall**: separately sample link deals, natural conversation deals, training and project cooperation.
- **Feedback reuse**: a confirmed exclusion or false positive must not reappear under the same key.
- **Digest reading time**: the default 24-hour report should be scannable in about three minutes.
- **Topic usefulness**: topic headings should name a real project, event, question or disagreement; generic extraction labels do not count.
- **Format parity**: final Markdown and final HTML must contain the same semantic conclusions and action ranking.
- **Coverage honesty**: incomplete indexing must show a gap rather than “no new information”.

Keep raw transcripts out of the public test suite. Convert real corrections into small synthetic fixtures that preserve the failure pattern without names, IDs or confidential commercial details.
