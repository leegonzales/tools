# bin/

Fleet shell helpers. Plain zsh, no dependencies beyond the `claude` CLI.

| Script | What it does |
|--------|--------------|
| `claude-token-harvest LABEL` | Mints a long-lived Claude Code OAuth token for one account (`claude setup-token`, browser login), then saves it to `~/.config/claude-env/tokens/LABEL.token` (mode 0600, dir 0700). You paste the token from the clipboard; it is never printed in full or put on a command line. |
| `claude-as LABEL [claude args...]` | Runs `claude` billed to the account saved as LABEL. Refuses if the token file is missing or not mode 600. Settings, skills, CLAUDE.md and memory stay shared; only the account changes. Sets `CLAUDE_ACCOUNT_LABEL`. |

Neither script contains a secret. They only reference the token directory path.

## Install

Symlink them onto your `PATH` so the repo stays the source of truth:

```sh
ln -sf "$PWD/bin/claude-as" ~/.local/bin/claude-as
ln -sf "$PWD/bin/claude-token-harvest" ~/.local/bin/claude-token-harvest
```

## Use

```sh
claude-token-harvest b                      # once per account
claude-as b --model claude-sonnet-5-5       # run Claude Code as account b
```

## Limits

`claude-as` clears `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and the cloud-provider flags, but it cannot override an `apiKeyHelper` in `~/.claude/settings.json`, which outranks the OAuth token. Do not set one if you use `claude-as`.
