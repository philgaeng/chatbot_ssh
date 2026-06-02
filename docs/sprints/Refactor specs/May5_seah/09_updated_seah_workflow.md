# 09 - Updated SEAH workflow (full utterance update extraction)

## Purpose

Consolidate all utterance and flow updates extracted from `NEP Chatbot - Comments.docx` into one implementation-ready reference for the May 5 SEAH refactor set.

---

## Scope of extracted updates

The extracted updates cover these chatbot flows:

1. SEAH Focal Point Flow
2. SEAH Complainant (Anonymous Victim-Survivor) Flow
3. SEAH Complainant (Identified Victim-Survivor) Flow
4. SEAH Complainant (Not the Victim-Survivor) Flow

---

## Cross-flow utterance/UI updates

Apply across relevant SEAH flows unless a flow-specific rule overrides:

1. Remove redundant hello text where opening welcome already exists.
2. Use updated intro copy:
   - "You are reporting a sexual exploitation, sexual abuse, or sexual harassment concern. All information you will provide will be treated with confidentiality."
3. Ensure person-identifying question order is consistent:
   - ask name before phone where name is retained in the flow.
4. Update restart/edit wording:
   - replace "Restart the process" with "Rewrite the summary."
5. Keep final acknowledgement text aligned with confidentiality and support-service guidance.

---

## SEAH focal point flow (confirmed + extracted updates)

1. **Focal point name**: mandatory and asked before phone.
2. **Focal point phone**: mandatory (cannot skip).
   - Matching should be against known **focal points** in the system (not listed complainants).
3. **Complainant consent question**: removed.
4. **Complainant name**: removed.
5. **Complainant phone**: removed.
6. **Complainant municipality**: remove from this intake flow.
   - Note: municipality can help project matching, but this field is not collected in this focal-point path under current decision.
7. **Other complainant location details** (`ward`, `village`, `address`): removed.
8. **SEAH incident summary** remains required and cannot be skipped:
   - "Please provide a brief summary of the SEAH incident."
9. **Employment linkage question** text update:
   - "Is the alleged perpetrator employed by an ADB project?" (`Yes` / `No`)
10. **Risk-related questions**: keep current risk list flow logic (see implementation note below).
11. **Follow-up question tied to complainant phone contact**: removed.

- Rationale: direct victim contact can be unsafe, and complainant profiling fields are now removed.

12. **Acknowledgement text**: update wording and include support-service referral note:

- "Thank you for reporting this incident. This confidential SEAH report has been submitted. Your reference number is XXX."
- "Please make sure to refer the complainant to proper support. Here are the possible support services: [list to be provided]."

13. **End button** preference from comments:

- one final button: "End session."

---

## Risk-button interaction constraint (implementation note)

Comment requests include replacing repeated prompts with multi-select. Current chatbot constraint remains:

- Use a **Done** button to stop risk selection.
- Use **Skip** in place of **None** when users may already have selected one or more items.

---

## End-of-session controls and safety behavior

Requested controls discussed:

- **Close Browser**
- **Close Session**

Decision status:

- Keeping both controls is acceptable in principle.
- However, **Close Browser is not a guaranteed privacy control** in current behavior because conversation history may still be visible when reopening the chatbot icon.

Safety note:

- Do not treat "Close Browser" as equivalent to secure conversation erasure.
- Until stronger containment is implemented, "Close Session" should be treated as the reliable in-flow termination action.

---

## SEAH complainant (anonymous victim-survivor) flow updates

1. Remove redundant hello text.
2. Use updated confidentiality intro text.
3. Keep phone question as optional with skip:
   - "Please enter your phone number so we can contact you for any needed follow-up. You may skip if you do not want to share it."
4. Add missing email question (optional with skip):
   - "Please enter your email address so we can contact you for any needed follow-up. Skip if you do not want to share it."
5. Update municipality prompt text:
   - "To provide the Municipality where the incident happened, please enter a valid municipality name. You may Skip if you do not want to share or you do not know the location."
6. If user chooses add-details path, use:
   - "Please enter additional details."
7. Insert missing consent-for-follow-up question before acknowledgement if it is still missing:
   - "Do you agree to being contacted for follow-up?"
   - Options: `Phone only`, `Email only`, `Phone and email`, `No`
8. Acknowledgement copy update:
   - "Thank you for reporting this incident. This confidential SEAH report has been submitted. Your reference number is XXX."
   - "Here are the support services that may help victim-survivors: [list to be provided]."

---

## SEAH complainant (identified victim-survivor) flow updates

1. Align text updates with anonymous victim-survivor flow where applicable.
2. Use updated name prompt:
   - "Please enter your full name. We recommend you to enter your first name, middle name and last name for better identification. You may Skip if you want to be anonymous."

---

## SEAH complainant (not the victim-survivor) flow updates

1. Align text updates with preceding SEAH complainant flow updates where applicable.
2. Consent sequence rule:
   - Ask "Did the victim-survivor agree that you file this complaint?" (`Yes` / `No`).
3. If user selects `No`, add follow-up:
   - "Is there an immediate danger to the life of the victim-survivor?"
4. If user selects `No` on immediate danger, use this final acknowledgement:
   - "Thank you. Here are the potential support services that can help the victim-survivor: [list to be provided]."
5. Ask reporter name before phone number.
6. Use updated name prompt:
   - "Please provide your full name. You may skip if you want to be anonymous."

---

## Final decisions and remaining dependency

1. **Support-service list wording**: not available yet.
   - Keep placeholder text (`[list to be provided]`) until the validated list is shared.
2. **Risk-selection UX**: keep `Done/Skip`.
   - Do not redesign to true multi-select + `None` at this stage.
3. **End-button placement/privacy hardening**:
   - Move the end buttons from inside the chatbot chat box to the persistent bottom composer area, just above the user text-input box.
   - This is the agreed immediate mitigation for visibility/safety concerns.

---

## Frontend implementation note (webchat UI contract)

This section is the implementation contract for the webchat team.

1. `Close Browser` and `Close Session` must be rendered as persistent **UI controls**, not as regular chatbot message buttons.
2. Placement must be in the bottom composer area:
   - in the same control zone as attachment/send controls,
   - directly above the `Type your message here...` input.
3. These controls must remain visible in SEAH flow states where session-close actions are expected.
4. Keep button actions mapped to existing payload handlers:
   - `Close Browser` -> `/nav_close_browser_tab`
   - `Close Session` -> `/nav_clear`
5. Message-level quick-reply rendering for these two actions should be disabled/ignored to avoid duplicate button sets in chat history.
6. This is a UI-layer placement requirement; backend action routing remains unchanged.
