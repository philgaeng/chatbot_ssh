# Scoped Refactor: Overview and Decisions

## Scope

Build a **minimal proof-of-concept** for the Orchestrator + Action Layer approach using only the **grievance details flow**:

```
Intro + main_menu → action_start_grievance_process → form_grievance loop → done
```

**Success criterion**: Same behavior as Rasa for this flow, validated via curl or simple test harness.

---

## Overall Progress

| Component | Spec | Status |
|-----------|------|--------|
| Orchestrator | [01_orchestrator.md](01_orchestrator.md) | ✅ Done |
| Action Layer | [02_action_layer.md](02_action_layer.md) | ✅ Done |
| Form Loop | [03_form_loop.md](03_form_loop.md) | ✅ Done |
| Flow Logic | [04_flow_logic.md](04_flow_logic.md) | ✅ Done |
| Agent Specs | [05_agent_specs.md](05_agent_specs.md) | ✅ Done |
| Test Spec | [06_test_spec.md](06_test_spec.md) | ⬜ Pending |

---

## Components

| Component | Spec | Purpose |
|-----------|------|---------|
| Orchestrator | [01_orchestrator.md](01_orchestrator.md) | FastAPI app, POST /message, session store, state machine |
| Action Layer | [02_action_layer.md](02_action_layer.md) | CollectingDispatcher, SessionTracker, action registry |
| Form Loop | [03_form_loop.md](03_form_loop.md) | Orchestrator drives extract → validate → ask |
| Flow Logic | [04_flow_logic.md](04_flow_logic.md) | States, transitions, actions for grievance details flow |

---

## Decisions (Answered)

### 1. Sensitive content detection
**Decision**: Exclude for spike. Treat sensitive content as normal text; validate adapter pattern first.

### 2. Celery classification
**Decision**: Stub for spike. No Celery call; orchestrator transitions to "done" directly.

### 3. Database
**Decision**: Use real DB as built. Essential for a meaningful proof-of-concept.

### 4. Domain / config source
**Decision**: Use our own YAML structure from the start. Extract all data from Rasa YAMLs into our format.

- Define orchestrator YAML schema (`flow.yaml`, slots) as the source of truth.
- Add an extraction step/script that reads `domain.yml` (and stories/rules if needed) and produces our YAML.
- Orchestrator loads only from our YAML. No dependency on Rasa format at runtime.
- When Rasa is removed, we keep the same structure – no rework.

**Flow**:
```
Rasa YAMLs (domain.yml, stories, rules)
        ↓
  [extraction script]
        ↓
Orchestrator YAMLs (flow.yaml, slots, etc.)
        ↓
  Orchestrator loads at startup
```

### 5. Language
**Decision**: Use `get_utterance` from the beginning – support both en and ne from the start.

### 6. Package location
**Decision**: `orchestrator/` at repo root – clear separation from Rasa and backend.

### 7. Intro / main menu
**Decision**: Include. Easier to design without Rasa form constraints.

---

## Out of Scope (This Spike)

- form_contact, form_otp, action_submit_grievance
- form_sensitive_issues, sensitive content branching
- Frontend integration (curl / test harness only)
- Celery classification trigger
- Message deduplication (message_id)
- Persistent session store (Postgres/Redis)
