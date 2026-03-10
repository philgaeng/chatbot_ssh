# Messaging Rules – WhatsApp and SMS (Staff Notifications)

This document defines **rules and constraints** for using WhatsApp and SMS for ticketing notifications (staff-facing: escalation alerts, links to tickets). It does not cover complainant-facing messaging (status updates to complainants), which may use the same or different channels.

---

## 1. Context

- **Goal:** Staff receive notifications (escalations, assignments) and can monitor activity. Preferred channel for many staff is **WhatsApp** (familiar, group culture).
- **Constraint:** WhatsApp Business API does **not** support posting into groups; only 1:1 messages to phone numbers. Getting full WhatsApp Business approval (verified business, templates) can be **difficult** (verification time, template approval, cost).
- **Fallback:** **SMS** has no 24-hour session limit and is often easier to integrate for outbound notifications; approval is typically simpler than WhatsApp.

---

## 2. Rules for Staff Notifications

### 2.1 No PII in Messages

- **Rule:** Notifications (WhatsApp or SMS) must **not** contain complainant PII (name, phone, address).
- **Content allowed:** Ticket/grievance ID, short summary (e.g. category, municipality), status change, **link** to the ticket (gsheet row, backend UI, or deep link). Example: `Escalation: grievance #abc123 – Road safety, KL Road. [Link to ticket]`.
- **Rationale:** Reduces leakage if messages are forwarded or screenshotted; keeps audit in the system, not in chat history.

### 2.2 WhatsApp: 1:1 Only (Links, No Group Posting)

- **Rule:** Use WhatsApp only for **1:1** messages from the system to staff. Send notification text + link only.
- **Limitation:** The official API cannot post into a group. Do not use unofficial/ToS-violating methods (e.g. automation that posts to groups via a personal account).
- **Human bridge:** One dedicated person receives all 1:1 notifications (or a digest) and **forwards them manually** into the appropriate **resolution-center WhatsApp groups**. Boss and others then monitor in groups natively.
- **Alternative for boss:** Send all escalation/activity to the boss’s number in a single 1:1 thread (his "monitoring feed"); no group needed for him.

### 2.3 No Pictures or Files in Groups – Folder Links Only

- **Rule:** In resolution-center WhatsApp groups, **do not** post pictures or file attachments (screenshots, PDFs). Post **links only** (to shared folder or specific file).
- **Rationale:** Attachments in WhatsApp are stored in chat, re-shared, and not access-controlled. Keeping files in a shared folder (with permissions and audit) and sharing links keeps PII and evidence under control.
- **Operational:** Staff upload screenshots/docs to the shared folder, then paste the link in the group (or the bridge person does it when forwarding).

### 2.4 SMS as Primary or Fallback for Notifications

- **Recommendation:** Treat **SMS** as the default or fallback channel for automated staff notifications (escalation, assignment). No template approval, no 24-hour window, simpler provider integration.
- **Use WhatsApp** where it is already approved and where staff strongly prefer it; otherwise use SMS for reliability and to avoid WhatsApp Business approval delays.

### 2.5 WhatsApp Business Approval (If Used)

- **Reality:** Full WhatsApp Business API use (sending proactive notifications) often requires:
  - Business verification (can be slow for NGOs/gov).
  - Pre-approved **templates** for outbound messages (each template approved by Meta; changes take time).
  - Per-conversation or per-message pricing.
- **Practical:** If WhatsApp approval is difficult, **rely on SMS** for system-initiated notifications and use WhatsApp only for staff-to-staff or human-bridge forwarding (no bot posting required).

---

## 3. Operational Model (Summary)

| Role | Channel | Behaviour |
|------|---------|-----------|
| **System → Staff** | SMS (preferred) or WhatsApp 1:1 | Notification + link only; no PII. |
| **Bridge person** | Receives 1:1 notifications | Forwards to resolution-center WhatsApp groups (text + link only). |
| **Boss** | 1:1 digest or group (via bridge) | Monitors in WhatsApp; no files in group, links only. |
| **Groups** | WhatsApp | No pictures/files; only links to shared folder. |

---

## 4. Compliance and Safety

- **Audit:** All contact-reveal events and (where applicable) notification sends are logged (who, what, when).
- **Training:** Staff and boss are trained on: no PII in messages, no attachments in groups (links only), and that discussions with complainants should be documented (screenshots) and attached to the ticket – see [07_gsheet_ticketing_spec.md](07_gsheet_ticketing_spec.md).

---

## 5. References

- Gsheet ticketing and PII: [07_gsheet_ticketing_spec.md](07_gsheet_ticketing_spec.md)
- Escalation and notifications: [Escalation_rules.md](Escalation_rules.md), [03_ticketing_api_integration.md](03_ticketing_api_integration.md)
