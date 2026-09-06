# Group Digest Design

## Goal

Turn a user-selected chat window into a compact, source-checkable report that answers:

1. What was discussed, and when?
2. What were the main themes?
3. What deserves attention?
4. Which deal, money, cooperation, training, project, event, or hiring signals are actionable?

The report is an action surface, not a transcript replacement.

## Evidence Behind The Design

- [QMSum](https://aclanthology.org/2021.naacl-main.472/) shows why one generic summary is insufficient for long, multi-topic meetings and motivates locate-then-summarize for user-focused questions.
- [An Exploratory Study on Long Dialogue Summarization](https://arxiv.org/abs/2109.04609) found retrieve-then-summarize effective for long dialogue, where relevant information is sparse and context-dependent.
- [Hierarchical Summarization for Longform Spoken Dialog](https://dl.acm.org/doi/10.1145/3472749.3474771) motivates semantically coherent segments and multiple summary depths.
- [Tilda](https://www.microsoft.com/en-us/research/publication/making-sense-of-group-chat-through-collaborative-tagging-and-summarization/) found that structured discourse signals and summaries help people make sense of unstructured group chat.
- [Slack AI summaries and recaps](https://slack.com/help/articles/25076892548883-Guide-to-AI-features-in-Slack) support custom date ranges, short recaps, and expandable sources.
- [Microsoft Teams Copilot chat summaries](https://support.microsoft.com/en-US/teams/copilot/how-to-use-microsoft-365-copilot-in-teams-chats-and-channels) separate main points, actions, and decisions, then let users open cited source messages.
- [Zulip topics](https://zulip.com/help/introduction-to-topics) show why the conversation or group should remain the primary navigation unit while topic segments organize discussion inside it.
- [GitHub collapsed sections](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections) provide a portable `<details>` disclosure pattern for Markdown.
- [BERTopic](https://github.com/MaartenGr/BERTopic) offers hierarchical and dynamic topic modeling, but is an optional advanced dependency rather than a v0.1 requirement.

Related open-source implementations reviewed include [microsoft/tilda](https://github.com/microsoft/tilda), [silverstein/minutes](https://github.com/silverstein/minutes), [SakethKanchi/parley](https://github.com/SakethKanchi/parley), and [masuidrive/slack-summarizer](https://github.com/masuidrive/slack-summarizer).

## Current Pipeline

```text
exact time window
  -> identify system/noise and in-group recap messages
  -> retain recaps as a secondary index, exclude them from primary evidence
  -> split on inactive time gaps
  -> group messages by topic inside each time session
  -> extract typed signals
  -> rank actionable items and discussion candidates separately
  -> render deterministic Markdown + optional machine HTML + compact editorial packet + evidence appendix
  -> Codex/Claude semantic editorial pass
  -> render topic/event-led final Markdown with group evidence drilldown
  -> optionally convert the final Markdown to HTML when interactive reading is useful
```

Signal types are independent:

- brand deal
- training
- project cooperation
- event
- hiring/outsource
- money/reward

Cross-group paid-boost links are aggregated once and do not reappear in every group summary.

In-group digests are handled separately from source conversation. Text recaps are detected from explicit recap headings. Image recaps can be configured by group, publisher, and optional posting time window. They remain discoverable as a secondary index but never become topics, key quotes, opportunity evidence, or actions. This prevents recursive "digest of a digest" output while preserving a route back to the original post.

## Presentation Contract

The deterministic report contains:

1. Scope and one-glance counts.
2. Items requiring action or verification.
3. One collapsible section per active group, beginning with a one-sentence extraction summary.
4. Compact topic tags, group events, evidence, and actions inside each group.
5. Links to the evidence appendix, structured exports, and a separate cross-group link index.
6. An optional in-group recap index that is visibly marked as secondary material.

Each noteworthy thread contains:

- time range
- theme
- what the discussion was about
- why it matters
- message and participant counts

The machine HTML report is optional and exists for extraction debugging. The appendix keeps all extracted discussion threads and representative evidence. Raw chat remains local. The user-facing HTML, when requested, is rendered from the completed semantic Markdown so Markdown and HTML do not disagree about the actual conclusions.

The final user-facing brief is produced from `group_daily_editorial_packet.json`, not by paraphrasing the deterministic scan. The editorial pass first clusters real projects, events, questions and disagreements across groups, then keeps group sections as source navigation. This preserves the “what happened” overview and the “where did it happen” audit path without pretending that regex-selected quotes are a semantic summary.

## Separate Private-Chat Digest

Group recap and relationship follow-up answer different questions and should not share one long body:

- `group-daily`: what each group discussed, plus group-sourced opportunities.
- `contact-daily`: which priority contacts need a reply, which are waiting, and what response direction fits the latest context.
- `brief`: a short cross-surface overview after both sources are refreshed.
- `cross_group_links.md`: one deduplicated URL index, kept outside both narrative reports.

The private-chat digest includes Profile-labeled contacts, open opportunities, and previously unlabeled chats only when the window contains a two-way commercial conversation. This prevents official accounts and ordinary personal chats from flooding the relationship report.

## Later Validation

- Measure precision of the first ten actionable items.
- Record false positives by signal type and group type.
- Compare 30, 45, and 60 minute inactivity gaps.
- Compare semantic editorial quality against deterministic-only output on the same historical windows.
- Measure whether users open group details and which filters they use in the static HTML report.
