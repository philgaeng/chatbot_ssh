# Officer Portal UI — Specification

> **Status:** As-built, July 2026. Consolidated from sprint docs (`docs/sprints/archive/claude-tickets/UI_SPEC.md`, `UI_DESIGN_SYSTEM.md`, `UI_HANDOFF_thread_redesign.md`, `UI_REVIEW.md`, `queue-tile-logic.md`).
> This folder is the permanent home for the ticketing-ui specification. The sprint docs above are historical snapshots; where they disagree with this folder, **this folder wins**.

## Contents

| Doc | Covers |
|-----|--------|
| [`01_ui_spec.md`](01_ui_spec.md) | Routes and navigation, queue (tabs + summary tiles), ticket thread (4-context bubble system), tasks, viewers/tiers, @mention and # commands, desktop ticket-detail layout, mobile `/m` app, SLA colour rules, SEAH treatment, accessibility + South/Central Asia UX research |
| [`02_design_system.md`](02_design_system.md) | Colour palette constraints, WCAG floors, icon library rules, semantic design tokens, status/priority/SLA badge maps, section-header pattern, no-emoji rule |

## Related docs

- `docs/ticketing_system/15_ticket_queue_search_and_filters.md` — queue search/filter bar + **Appendix A: queue summary tile logic** (resolution of the tile bug reported in `docs/sprints/archive/claude-tickets/queue-tile-logic.md`)
- `docs/ticketing_system/11_roles_and_permissions.md` — role definitions behind tab/tier visibility
- `docs/ticketing_system/12_workflows_configuration.md` — workflow steps rendered by the stepper

## Code entry points

| Area | Path |
|------|------|
| App (Next.js 16 / React 19 / Tailwind v4) | `channels/ticketing-ui/` |
| Route pages | `channels/ticketing-ui/app/` |
| Shared thread components | `channels/ticketing-ui/components/thread/` |
| Bubble/task/event constants | `channels/ticketing-ui/lib/mobile-constants.ts` |
| Design tokens | `channels/ticketing-ui/lib/design-tokens.ts` |
| Icon aliases | `channels/ticketing-ui/lib/icons.tsx` |
| Auth (Keycloak PKCE OIDC) | `channels/ticketing-ui/lib/auth/oidc-auth.ts`, `app/providers/AuthProvider.tsx` |
| Mobile/desktop route mapping | `channels/ticketing-ui/lib/mobile-routes.ts` |
