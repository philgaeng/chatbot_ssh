# Follow-up — a tracked file is rewritten as an import side effect

> **Raised:** 2026-08-19, while fixing [D-26](../PROGRESS.md) — it kept appearing in `git status`
> after every containerised test run, and I reverted it twice before asking why.
> **Logged as deviation D-47** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🔵 open · **Size:** S to fix, M to be sure nothing depended on the old behaviour
> **Not fixed here** because it lives in `backend/task_queue/`, a stable chatbot service, and
> CLAUDE.md asks for deliberate intent and tests there — not a drive-by edit inside a CI commit.

---

## The finding

`backend/task_queue/config.py` ends with a bare call at module scope:

```python
# Update shell config when this module is imported
update_shell_config()
```

`update_shell_config()` writes **`backend/scripts/task_queue/config.sh`** — a file that is
**tracked in git** — from the process's current environment, and `chmod 0755`s it.

So: importing `backend.task_queue.config` rewrites a committed file. The value that lands depends
on where the import happened.

| Where the import ran | What gets written |
|---|---|
| Inside the compose stack | `REDIS_HOST="redis"` |
| On the host | `REDIS_HOST="localhost"` |

## Why it matters more than the one-line diff suggests

* **The working tree goes dirty on its own.** Every containerised test run leaves a modified file
  that nobody edited. During D-26 it was swept into `git add -A` and had to be pulled back out of
  a commit — which is exactly how an unrelated, environment-specific value gets shipped.
* **Last runner wins.** The committed content records whichever environment most recently imported
  the module, which is not a fact about the project.
* **It is invisible.** Nothing announces it; the file simply changes. Both times I noticed, it was
  because `git status` disagreed with what I had done, not because anything reported it.

## What it is not

Not a security problem, and not currently breaking anything — the value is a hostname, and the
consumers that source this file (`scripts/task_queue/*.sh`, the systemd unit path in
`docs/deployment/`) get a *correct* value for the environment they run in. That is presumably why
it was written this way. The cost is repository hygiene, not runtime.

## Recommendation

**Generate to an untracked path and stop tracking the artefact.** Write to
`backend/scripts/task_queue/config.generated.sh`, add it to `.gitignore`, and have the consumers
source that. Keep a tracked `config.sh.example` if the shape needs documenting.

Two weaker options, for the record:

* **Write only on explicit request** (`python -m backend.task_queue.config --write-shell-config`,
  called from the deploy script). Cleanest semantically — an import should not touch the disk —
  but it moves the responsibility to every caller, and a missed caller fails at deploy time.
* **Write only when the content would change.** Removes the churn, keeps the surprise.

⚠ Before any of these, check what actually sources the file. `grep -rn "task_queue/config.sh"`
finds the deploy path; a stale or missing file there breaks worker startup, which is a worse
failure than a dirty `git status`.
