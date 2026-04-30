# SEAH Ticketing System Questions (Moved from Intake Spec)

This file captures questions related to complaint treatment in the ticketing/back-office system, separated from chatbot intake flow decisions.

Source spec: `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

---

## Access control and audit

17. Which user roles can view SEAH records in v1 (exact role names)?
- Current answer: out of scope

18. Should all SEAH record reads/writes require audit logging with actor, timestamp, and action?
- Current answer: out of scope - ticketing system

19. Confirm 2FA rollout scope:
- A) required only for SEAH reviewer/admin users now, or
- B) required for all back-office users.
- Current answer: out of scope - ticketing system

20. Confirm if there is a break-glass emergency access policy for SEAH cases.
- Current answer: what does that mean
- Clarification: break-glass means a controlled emergency override process for temporary access to restricted SEAH records when urgent intervention is required. Access is typically time-limited and fully audited.

---

## Notifications and internal handling

22. Should internal SEAH team notifications be sent (email/in-app queue/webhook), and if yes through which channel?
- Current answer: DECIDED - email

---

## Investigator workflow and post-intake handling

30. Should investigators have a separate internal workflow endpoint for follow-up updates outside chatbot?
- Current answer: out of scope - ticketing system
