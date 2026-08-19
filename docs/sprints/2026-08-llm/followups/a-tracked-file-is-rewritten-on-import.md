# Follow-up — a tracked file was rewritten as an import side effect

> **Raised:** 2026-08-19, while fixing [D-26](../PROGRESS.md) — it kept appearing in `git status`
> after every containerised test run, and I reverted it twice before asking why.
> **Logged as deviation D-47** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ✅ **CLOSED 2026-08-19, same day.** **Size, in the event:** S — a deletion, not the
> redirection this document first recommended. See §The correction.

---

## The finding

`backend/task_queue/config.py` ended with a bare call at module scope:

```python
# Update shell config when this module is imported
update_shell_config()
```

`update_shell_config()` wrote **`backend/scripts/task_queue/config.sh`** — a file **tracked in
git** — from the importing process's environment, and `chmod 0755`'d it.

So importing `backend.task_queue.config` rewrote a committed file, and the value that landed
depended on where the import happened:

| Where the import ran | What got written |
|---|---|
| Inside the compose stack | `REDIS_HOST="redis"` |
| On the host | `REDIS_HOST="localhost"` |

## Why it mattered more than the one-line diff suggested

* **The working tree went dirty on its own.** Every containerised test run left a modified file
  nobody had edited. During D-26 it was swept into `git add -A` and had to be pulled back out of a
  commit — which is exactly how an unrelated, environment-specific value gets shipped.
* **Last runner won.** The committed content recorded whichever environment most recently imported
  the module, which is not a fact about the project.
* **It was invisible.** Nothing announced it; the file simply changed. Both times it was noticed,
  it was because `git status` disagreed with what had been done, not because anything reported it.

The file's entire history bears this out: since `8ec9057a` created it, every commit touching it is
`REDIS_HOST` alternating between the two values, carried into unrelated commits — three of them in
this sprint alone.

---

## The correction

> ⚠ **This document originally said "the deploy path sources this file — a stale or missing one
> breaks worker startup," and recommended generating to an untracked path instead of deleting.
> That was wrong, and it was wrong in a way worth naming: I read `grep -rn "config.sh"`, saw
> `source scripts/database/config.sh` in `scripts/docker/init_db.sh`, and attributed it to this
> file. There are two different `config.sh` files in this repository, and that hit belongs to the
> other one.**
>
> The caution was doing real work — it is why the fix was deferred out of the D-26 commit instead
> of being made blind, and deferring it was still right. But a caveat asserted from a grep that
> was never narrowed is a guess wearing the clothes of a finding, and it nearly bought a
> generate-to-untracked-path mechanism for an artefact that should simply not exist.

**Nothing sourced `backend/scripts/task_queue/config.sh`.** Verified three ways:

1. `backend/scripts/task_queue/` contained **only** `config.sh` — no sibling shell scripts.
2. No reference to it anywhere outside `config.py` itself: not in `deployment/`, not in any
   systemd unit, not in `scripts/`. (`scripts/README.md` mentions a top-level `scripts/task_queue/`
   — a different path, and one that no longer exists either.)
3. Its consumers, the legacy systemd/shell runtime scripts, were removed in **`28508aec`**
   ("remove legacy runtime scripts and align docs to docker workflow") when the stack moved to
   Docker. The generator and its output were left behind.

## What was done

* **Deleted** `generate_shell_config()`, `update_shell_config()`, and the module-scope call
  (~78 lines), leaving a comment at the site explaining why and what to do if a shell runtime
  ever comes back.
* **Deleted** `backend/scripts/task_queue/config.sh`, and with it the now-empty
  `backend/scripts/` tree.
* Confirmed nothing else became dead: every configuration dataclass instance the generator read
  (`service_config`, `worker_config`, `resource_config`, …) still has external callers, and `Path`
  is still used elsewhere in the module.

**Pinned by** [`tests/backend/test_import_side_effects.py`](../../../../tests/backend/test_import_side_effects.py).

The test does **not** assert that the deleted function is gone — that would be satisfied by a
rename. It pins the property that made this a bug: **importing a module writes nothing to the
source tree.** It snapshots every source file under `backend/`, `ticketing/`, `scripts/` and
`channels/shared/`, imports each startup module in a **subprocess** (in-process would prove
nothing — pytest has already imported them, and a module-scope write happens once), and compares.
So it catches the next instance wherever someone writes it.

Mutation verified: re-introducing an import-time write turned it red, naming the created path.

## The transferable bit

A module-scope side effect is invisible in a way a function call is not — nobody imports a config
module expecting the disk to change. And **a generated artefact must never be tracked**: the moment
it is, every environment that runs the generator claims the file, and the repository records a
race rather than a decision. If a shell runtime returns, generate to an untracked path and
`.gitignore` it.
