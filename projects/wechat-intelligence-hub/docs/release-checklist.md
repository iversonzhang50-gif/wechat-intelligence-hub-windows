# Release Checklist

WeChat Intelligence Hub and its required read-only CLI are published together in the dedicated `wechat-intelligence-hub` repository. The whitelist build is a temporary privacy-audit candidate, not a separate Git repository and not the source used for `git push`.

1. Confirm that the repository root contains `LICENSE`, `NOTICE.md`, `SECURITY.md` and the Preview limitation in `README.md`.
2. Review `git status` and the complete staged diff. Publish only tracked source files.
3. From the repository root, run `./scripts/validate.sh`. It validates every Skill, runs source tests, builds this project from its public whitelist, and reruns its tests inside the temporary candidate.
4. Run the fictional-data demo: `bash projects/wechat-intelligence-hub/scripts/run_demo.sh`.
5. Inspect the temporary build's generated `release-manifest.json` when diagnosing a release. Do not commit a manifest generated for an earlier source state.
6. Confirm that the public tree has no real names, WeChat IDs, chatroom IDs, local paths, tokens, screenshots, databases, access material, generated reports, or old CLI binaries.
7. Verify the documented install flow from a fresh clone or clean temporary directory.
8. Tag the tested repository commit and create the GitHub Release from that exact commit.

Do not add `output/`, `tmp/`, `wechat-deal-radar/`, `config/profile.local.json`, real contact lists, local databases, access material, or any old `wechat-cli` source or binary to a release.
