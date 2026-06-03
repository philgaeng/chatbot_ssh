# REST Chatbot Production Documentation

This folder is the production documentation set for chatbot-specific behavior.

Scope of `docs/rest_chatbot`:

- Conversation engine and orchestration
- Chatbot request/response APIs and contracts
- Task and websocket behavior from chatbot perspective
- Frontend behavior in `channels/REST_webchat`
- Runtime configuration for chatbot features

Out of scope for this folder:

- Cross-project shared services (for example messaging) now documented in `docs/services`

## Document Map

- `docs/rest_chatbot/01_backend_spec.md`  
  Backend architecture and API contracts used by chatbot.

- `docs/rest_chatbot/02_flow_spec.md`  
  State machine, forms, action dispatch, and end-to-end conversational flow rules.

- `docs/rest_chatbot/03_frontend_spec.md`  
  Full `channels/REST_webchat` client spec (UI, events, payloads, upload, socket).

- `docs/rest_chatbot/04_operations_spec.md`  
  Runtime config, environment variables, startup, and production notes.

- `docs/rest_chatbot/workflow_maps/seah_intake_turn_map.json`  
  Structured turn map for SEAH intake.

- `docs/rest_chatbot/workflow_maps/turn_map.schema.json`  
  Schema for workflow map JSON assets.

## Shared Service Specs

Shared service documentation lives in `docs/services`.

Current shared service spec:

- `docs/services/05_messaging_service.md`
