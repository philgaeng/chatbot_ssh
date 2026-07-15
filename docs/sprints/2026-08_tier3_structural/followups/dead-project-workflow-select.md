# Follow-up — `ProjectWorkflowSelect` is dead code

> Opened by **T3-05** (2026-07-15, `dev/tier3-structural`). Found while moving, **not fixed** — per the spec's *"Out of scope — log, don't fix"* rule.

## The finding

`components/settings/workflows/ProjectWorkflowSelect.tsx` (was `app/settings/page.tsx:387` pre-extraction) has **zero callers**.

Verified repo-wide at extraction time:

```
$ grep -rn "ProjectWorkflowSelect" --include=*.tsx --include=*.ts . | grep -v node_modules
app/settings/page.tsx:387:function ProjectWorkflowSelect({
```

One hit — its own definition. It was **already dead before this sprint**: eslint flagged it in the 141-warning baseline (`'ProjectWorkflowSelect' is defined but never used`), tracked in [`../../2026-07_hardening/followups/portal-lint-cleanup.md`](../../2026-07_hardening/followups/portal-lint-cleanup.md).

It is superseded in practice by `ProjectWorkflowsEditor` (plural), which is what `ProjectEditor` actually renders.

## Why it wasn't deleted here

T3-05's prime directive is **move verbatim, zero behaviour change**; deleting code is a different act from moving it, and mixing the two makes a large move series unreviewable. Logged instead.

## ⚠️ Side effect worth knowing — the signal got quieter

Moving it into its own module **silenced its eslint warning**: `no-unused-vars` does not flag an *exported* symbol, and every component in the cluster is exported by convention. So the portal's warning count went **141 → 140** across T3-05.

That −1 is **not** an improvement. It is the dead-code signal being lost. The code is now *less* discoverable than it was inline, which is exactly why this file exists.

## What to do

Delete `components/settings/workflows/ProjectWorkflowSelect.tsx` and confirm nothing imports it (`grep -rn ProjectWorkflowSelect`). Expected effort: **XS**. Natural home: the `portal-lint-cleanup` sweep.

If it is *not* dead — i.e. someone intended to wire it up and never did — that is a missing feature and should become its own ticket rather than being left as an unreferenced module.

## Related

- [`settings-tab-render-tests.md`](settings-tab-render-tests.md) — sibling T3-05 follow-up.
- `portal-lint-cleanup.md` (Tier-1 hardening) — owns the 141-warning baseline.
