# Sprint summary — June 2026: Voice notes & UX (June5)

> Original specs: [`archive/June5/`](archive/June5/) + feature brief [`archive/voice-notes-and-ux-feature-brief.md`](archive/voice-notes-and-ux-feature-brief.md) · Status: **Delivered except TP-02 and TP-05 SMS wiring**

## Goal

Ship the voice-note intake, chatbot UX polish, portal usability round (TP-01…15), and the roles/permissions admin matrix (RP-01…11) defined in the voice-notes-and-ux feature brief.

## Delivered

- **Chatbot P1** (CB-03/04/05/07): close-button consolidation (standard = Close session, SEAH = Close browser), "file another grievance", attachment copy rewrite, 3-message post-submit sequence + grievance-filed banner.
- **Chatbot P2** (CB-01/06/08/09): voice-note intake (45s cap, multi-clip, status banner), map-pin location (`complainants.location_geo`), EXIF consent metadata, dust fast path expanded to **Road Hazard** (6 subtypes, preset taxonomy keys, deterministic classification `LLM_skipped`).
- **Portal P1** (TP-01…15): audio player, acknowledge-with-grievance thread card, call report, report share links (internal + public token), export-all XLSX, dashboard label clarity, command simplification + image gate + escalation form, supervisor-only assign + reassignment reason codes, friendly validation errors, **classification status model (Option B)** + hybrid read model/sync + officer validation gate (TP-14), complainant PII display/edit — standard decrypted, SEAH masked (TP-15).
- **Roles & permissions** (RP-01…11): `admin_scopes` table, 4 admin keys (`super_admin`/`org_admin`/`project_admin`/`officer_admin`), `workflow_track` on scopes, roles CRUD + archetypes, Settings visibility matrix.
- **Infra add-ons**: server-side image compression (libvips/HEIF, 1280px/q80, EXIF strip), resolved-case archiving & retention job.

## Where the durable content lives now

| Content | Permanent home |
|---|---|
| Classification status model | `docs/ticketing_system/17_classification_status.md` |
| Roles/admin matrix | `docs/ticketing_system/11_roles_and_permissions.md` |
| Chatbot flow/UX contracts (voice, close controls, road hazard, post-submit) | `docs/rest_chatbot/02_flow_spec.md`, `03_frontend_spec.md`, `docs/services/03_voice_grievance_service.md` |
| Image compression policy | `docs/services/04_file_processing_service.md` §6 |
| Archiving policy | `docs/ARCHIVING_AND_RETENTION.md` |
| PII display rules | `docs/seah/02_vault_privacy_and_reveal.md`, `docs/ticketing_system/08_ticket_resolution_and_case_summary.md` |

## Leftovers noted at close

- **TP-02**: officer-side voice transcription + manual fallback — not started.
- **TP-05**: report-share SMS dispatch — integration point left unwired.
- Production smoke/dry-run checklist items (image compression prod smoke, archiving prod dry-run) — unchecked.
- AD-01…03 program-level items from the brief — not scheduled.
