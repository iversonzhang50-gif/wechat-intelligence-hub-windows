# Access bundle compatibility

`rion-wechat-cli import-access` converts either of these user-supplied local JSON formats:

1. a path map whose non-metadata entries map database-relative paths to a hexadecimal key string or an object containing `enc_key`/`key`;
2. a schema-2 salt map containing `schema_version: 2` and `keys`, where each 32-hex database salt maps to its 64-hex post-PBKDF2 `enc_key`.

The path-to-`enc_key` convention is compatible with the Apache-2.0-licensed public project [huohuoer/wechat-cli](https://github.com/huohuoer/wechat-cli), version `0.2.4` at the time this compatibility layer was implemented. This repository does not copy, bundle, execute, or document that project's process-memory scanners, re-signing helpers, or bundled native key finder.

The salt-to-`enc_key` schema-2 convention is compatible with the MIT-licensed module [`github.com/r266-tech/wechat-cli`](https://pkg.go.dev/github.com/r266-tech/wechat-cli), version `v1.6.21`. Its public `internal/config` and `internal/wcdb` contracts define the map as the first 16 bytes of each encrypted database, encoded as 32 lowercase hex characters, to a 32-byte post-PBKDF2 key encoded as 64 hex characters. Only this published data contract was used in the Reader conversion layer; that layer does not invoke any acquisition tool. Separately, the optional [experimental access helper](../../../skills/wechat-cli/references/experimental-access.md) can explicitly invoke a user-supplied, reviewed wxkey build. No upstream acquisition implementation or binary is bundled.

Import is explicit. The command never searches another tool's state directory. The source must have `0600` permissions, every database path must remain inside `--database-root`, key values are never returned in command output, and the destination is written with `0600` permissions. Verification uses the local SQLCipher runtime against private snapshots before the destination file is committed.

Example with placeholders only:

```bash
chmod 600 /path/to/user-authorized-access.json
rion-wechat-cli import-access \
  --source /path/to/user-authorized-access.json \
  --keys-file ~/.config/rion-wechat-reader/keys.json \
  --pretty
```

For a schema-2 salt map, `db_root` is read from that explicitly supplied private file. A path map has no authoritative embedded root and must additionally provide `--database-root /path/to/authorized/db_storage`. After verification, the normalized root is retained only in the private `0600` destination bundle so a subsequent `setup --keys-file ...` can reuse it without another path argument.

The command supports conversion of access material the user already possesses. A schema-2 config can also be passed directly through an explicit `--keys-file` option. The CLI reads a database's 16-byte header salt, selects the matching entry, and uses SQLCipher's 96-hex raw-key form (`enc_key + salt`) against a private snapshot. It does not obtain, scan, recover, or derive database keys.
