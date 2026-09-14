# Item — `GRM-093` a pulling deploy never authenticates, so it cannot pull a private package

**Origin:** agent discovery, 2026-09-14 — found while preparing the staging deploy in [PR #10](https://github.com/philgaeng/chatbot_ssh/pull/10).
**Lane:** `standing` · **Reported:** 2026-09-14 · **Closes the code half of `A-11`.**

## 1. What is wrong

[`03_operations.md`](../deployment/03_operations.md) §6a says **"Staging pulls images that CI
already built"**, and `make aws-deploy` sets `DEPLOY_BUILD=0` to do exactly that. But
[D-010](../DECISIONS.md) made the repository private on 2026-09-04, so its GHCR packages are
private — and `REMOTE_ACQUIRE_IMAGES` went straight to `compose pull` with **no `docker login`
anywhere in the Makefile**, and no registry credential in `.env.shared`'s `#@secret` manifest.

**Measured 2026-09-14:** `grep -n "docker login" Makefile` → nothing. The documented capability
fails on the host with `denied`, at the point of a deploy, which is the worst place to find out.

## 2. Kind — the four questions

1. Does a live spec claim this behaviour? **Yes** — §6a, quoted above. → continue.
2. Does the code disagree with that spec? **Yes.** And the spec is **wrong**: it describes a
   pulling deploy without naming its precondition, which stopped being optional on 2026-09-04.

> **kind:** `deviation`
> **why this kind:** §2.3 decided it. It began as a bug — until fixing it meant editing §6a to add
> the credential requirement, and that edit is the moment the fork appears. Reclassified rather
> than shipped as a bugfix that quietly rewrites a spec.

## 3. Profile

| ✓ | Question | Fires |
|---|---|---|
| ✗ | Changes user-visible behaviour | — deploy plumbing; no complainant or officer sees it |
| ✗ | A UI surface changes shape | — |
| ✗ | Schema changes | — |
| ✔ | **PII · auth · SEAH · complainant channel · new external egress** | **`G-SENSITIVE`** |
| ✗ | API or event shape changes | — |
| ✔ | Deployed | `G-RELEASE` |
| ■ | *(always)* | `G-TEST` |

> **profile:** `deviation` `+SENSITIVE` `+RELEASE` · **gates:** SPEC · SENSITIVE · TEST · RELEASE
> **model:** Opus — mechanically, from `+SENSITIVE` · **size:** S

⭐ **`G-SENSITIVE` fires on two of its five triggers, and neither is about diff size** (rule 4.2).
It introduces **a credential** into the deploy path, and it makes the host **authenticate to an
external service** it previously only fetched from anonymously. A three-line Makefile change is
not a chore when that is what the three lines do.

**Boundary tests named, per the gate:**

- the token is never an argv argument (`--password-stdin` only) — `ps` on the host would otherwise
  expose it to every process
- the token value is never echoed by a deploy that prints a great deal
- an absent token **skips** rather than fails — so `make wsl-up`, `DEPLOY_BUILD=1`, and any
  public-registry host are provably unaffected

## 4. What was built

`REMOTE_REGISTRY_LOGIN` in the Makefile, called from the **pull arm only** of
`REMOTE_ACQUIRE_IMAGES`, after the no-`IMAGE_TAG` guard. Registry host and owner are derived from
`IMAGE_REGISTRY`, so a different registry needs no second place to edit.

Pinned by [`tests/repo/test_registry_login.py`](../../tests/repo/test_registry_login.py) — 5 checks,
three of which were **red before the fix**.

## 5. ⚠ What this does NOT do — the manual half of `A-11` is still the owner's

- **The token does not exist yet**, and this change cannot create it: a **classic** PAT with
  `read:packages` and no other scope. ⚠ **Not fine-grained** — verified against GitHub's docs
  2026-09-14: *"GitHub Packages only supports authentication using a personal access token
  (classic)."* `A-11` recommends fine-grained and is **wrong**; see `A-11`'s own evidence, a
  `403: Resource not accessible by personal access token`, which is that limit and was read as
  something else. ⚠ A classic PAT cannot be scoped to one repo — read-only and no second scope
  is the whole control.
- **`#@secret GHCR_READ_TOKEN` is deliberately NOT added to `.env.shared`.** `gen_env_local.sh`
  fails when the two halves disagree *in either direction*, so a marker with no value in
  `secrets.enc.env` would break `make env-local` for everyone until the value landed. **Add both
  in one change** (`make secrets-edit`, then the marker, then `make env-local`).
- **`make env-local` must then be run on the staging host**, because `aws-deploy` deliberately
  does not run it (Makefile §"⚠ 'make env-local' on staging/prod is the dangerous one").
- **Unmeasured:** whether the staging host can reach `ghcr.io` at all. One command, same session:
  `curl -sI https://ghcr.io/v2/`.

Until all four are done the deploy still cannot pull — but it now **says so in one line** instead
of failing with `denied`, and `make aws-deploy DEPLOY_BUILD=1` remains the fallback that needs none
of them.

## 6. Register line

```
| `GRM-093` — a pulling deploy never authenticates, so it cannot pull a private package | deviation | deviation+SENSITIVE+RELEASE | `merged` · `tested` | S | standing | … |
```

## 7. Notes

⚠ **Residue, stated rather than hidden.** A successful `docker login` writes a base64 credential
into `~/.docker/config.json` on the host — not encrypted. That is *why* `A-11` specifies a
read-only, repo-scoped token: the scope of that token is the whole control, because the file
protecting it is not one.

⭐ **The test found a defect in itself.** `assert "compose pull" in out` passed vacuously — the real
expansion is `docker compose --env-file … --profile auth pull …`, so the literal never matched and
the assertion could not fail. The same mistake was in the `not in` direction, where it would have
gone green forever. Both now use a regex, and the lesson is in the file.
