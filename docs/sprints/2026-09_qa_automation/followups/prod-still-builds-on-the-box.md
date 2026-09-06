# Follow-up — production still builds its own images, and that is a decision with an expiry

**Logged:** 2026-09-06, as QA-02 landed. **Owner:** deployment · **Status:** deliberate, tracked
as `GRM-078`. The switch is built and tested; what is missing is one command run on the DOR host.

## What changed, and what did not

QA-02 made the deploy's pull-or-build choice a variable, `DEPLOY_BUILD`, and pointed the four
`aws-*` targets at `0` (pull). Everything else — including all four `prod-*` targets — keeps the
default `1` and builds on the host, exactly as before.

**Nothing about production's behaviour changed.** Make substitutes the literal at expansion
time, so the command that reaches the DOR box contains `if [ "1" = "1" ]` and takes the build
branch. Verified by diffing `make -n prod-deploy` across the change.

## Why production was not converted

**Nobody has run `curl -sI https://ghcr.io/v2/` from the DOR host.** It is VPN-only and the
owner's access is intermittent; as of 2026-09-06 they had not been able to reach it. Until that
returns a 200, "production pulls from GHCR" is a guess.

⚠ **Guessing wrong is expensive in a way guessing right is not cheap enough to justify.** The
failure would land on a VPN-only host, in a maintenance window, on the path with no quick
rollback — while the thing being fixed (an OOM during an on-box build) has never actually
happened on production, only on staging. The asymmetry favours waiting.

⚠ **A second blocker, discovered while writing the workflow:** the repository is **private**
([D-010](../../../DECISIONS.md)), so its packages are private, so a host that pulls needs a
credential. There is none — `.env.shared`'s `#@secret` manifest has no GitHub or registry token
at all. That is `A-11`, and it applies to staging first.

## Definition of done

- [ ] `curl -sI https://ghcr.io/v2/` from the DOR host — records whether it can reach the registry
- [ ] `uname -m` from the same session — settles `A-1`, and with it whether we build one
      architecture or two (the owner expects `x86_64`)
- [ ] A read-only registry credential exists on the host (`A-11`)
- [ ] `make prod-deploy DEPLOY_BUILD=0 IMAGE_TAG=<sha>` in a maintenance window, with
      `DEPLOY_BUILD=1` as the documented fallback in the same window
- [ ] The digest report is read, not skimmed — a pulling deploy that was not given a new tag
      succeeds while changing nothing

⭐ **Both host questions are one SSH session.** Pair them; the intermittent access is the
constraint, not the commands.

## If it turns out production cannot reach the registry

Then this is not a follow-up but a different ticket, and the options are `docker save`/`load`
over the VPN, or a registry mirror inside DOR. Neither is hard; both need to be chosen
deliberately rather than discovered.
