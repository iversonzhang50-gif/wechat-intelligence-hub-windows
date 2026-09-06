# Security and Privacy

WeChat Intelligence Hub processes private local chat data. Treat every real input and generated report as sensitive.

## Never Commit

- WeChat databases, keys, tokens, cookies, session material, or reader state
- Real contact lists, WeChat IDs, group names, avatars, or relationship maps
- Raw or summarized chat transcripts
- Generated reports, screenshots, media attachments, logs, or local SQLite databases
- `.env` files, `config/profile.local.json`, and machine-specific configuration

The repository `.gitignore` excludes the standard local paths, but it is not a substitute for reviewing the staged diff before every commit.
Do not publish by manually zipping the working directory: ignored local files can still be copied into an archive. Build releases from Git-tracked files only.

## Reporting A Vulnerability

Do not open a public issue containing chat samples, credentials, database fragments, local paths with personal identifiers, or screenshots of real conversations. Reproduce the problem with the fake sample data first.

## Operating Boundary

The project is read-only by design. It must not send messages, add contacts, transfer files, make payments, or mutate WeChat data. Third-party local readers can break after a WeChat upgrade; run the compatibility check before relying on a fresh report.
