# Agent Instructions: Replace AWS Cognito with Keycloak

## Mission

Replace AWS Cognito with self-hosted **Keycloak** so the GRM ticketing system
can be deployed on any server (not AWS-only). The backend auth dependency is
currently a **stub** returning a hardcoded mock user — this is the primary
integration target. The frontend uses a custom OAuth2 client that needs to be
re-pointed to Keycloak.

**Repo:** https://github.com/philgaeng/chatbot_ssh  
**Branch:** `feature/grm-ticketing`  
**WSL path:** `/home/philg/projects/nepal_chatbot_claude`  
**Docker compose:** `docker compose -f docker-compose.yml -f docker-compose.grm.yml`

---

## Technology Decision: Keycloak 26 (latest stable)

**Why Keycloak:**
- Battle-proven since 2013, backed by Red Hat / CNCF
- Direct Cognito equivalent: OIDC, OAuth2, SAML, MFA, user federation
- Single Docker container; official image `quay.io/keycloak/keycloak:26`
- Mature Admin REST API for user invite/management (replaces Cognito admin SDK)
- Claim mapping is fully configurable → we can keep the same JWT claim names
  the app already uses (`custom:grm_roles` etc.) with zero code changes in
  the business logic layer

**Not chosen:** Authentik (newer, less battle-tested for government/enterprise use).

---

## Current Auth Setup — Read These Files First

Before writing any code, read and understand:

| File | What it does |
|------|-------------|
| `channels/ticketing-ui/lib/auth/cognito-auth.ts` | Custom OIDC client — implements Authorization Code flow manually against Cognito endpoints |
| `channels/ticketing-ui/app/providers/AuthProvider.tsx` | React context — wraps `CognitoAuthClient`, handles bypass mode |
| `channels/ticketing-ui/.env.local` | Current env vars (all `NEXT_PUBLIC_COGNITO_*`, bypass flag) |
| `ticketing/api/dependencies.py` | FastAPI `get_current_user()` — currently a **stub returning mock-super-admin**, has clear `INTEGRATION POINT` comment with exact code to implement |
| `ticketing/api/routers/users.py` | Officer invite — currently deferred/stubbed, no real Cognito calls exist |
| `docker-compose.grm.yml` | GRM overlay — add Keycloak service here |
| `ticketing/config/settings.py` | Pydantic settings — add Keycloak env vars here |

### Key findings from the current code

**Frontend JWT claims** (from `CognitoAuthClient` / `TokenPayload`):
```typescript
"sub"                    // user_id
"email"
"name"
"custom:grm_roles"       // comma-separated role keys, e.g. "super_admin" or "site_safeguards_focal_person"
"custom:organization_id" // e.g. "DOR" or "ADB"
"custom:location_code"   // e.g. "NP_D006" (optional)
```

Configure Keycloak token mappers to emit these **exact claim names** so
`AuthProvider.tsx`, `CognitoAuthClient`, and the backend `get_current_user()`
need zero changes to their claim-reading logic.

**Backend** (`dependencies.py`): `get_current_user()` is a stub. The `INTEGRATION POINT`
comment inside it already shows the exact pattern to implement — just replace
`verify_cognito_token` with `verify_keycloak_token`.

**Dev bypass** (`NEXT_PUBLIC_BYPASS_AUTH=true`): Already implemented in `AuthProvider.tsx`
— injecting a mock `super_admin` user and skipping all OIDC. Must continue to
work after this change so development works without Keycloak running.

---

## What to Build

### 1. Keycloak service in `docker-compose.grm.yml`

Add to the existing GRM overlay. Use the existing `db` Postgres container with
a dedicated schema — no second database container.

```yaml
keycloak:
  image: quay.io/keycloak/keycloak:26
  command: start-dev   # development mode (no TLS required locally)
  # For staging/production: use 'start' + set KC_HOSTNAME, KC_HTTPS_* etc.
  environment:
    KC_DB: postgres
    KC_DB_URL: jdbc:postgresql://db:5432/app_db
    KC_DB_SCHEMA: keycloak
    KC_DB_USERNAME: user
    KC_DB_PASSWORD: password
    KC_HTTP_PORT: "8080"
    KC_HEALTH_ENABLED: "true"
    KEYCLOAK_ADMIN: admin
    KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:-admin}
  ports:
    - "8080:8080"
  depends_on:
    db:
      condition: service_healthy
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "exec 3<>/dev/tcp/localhost/8080 && echo -e 'GET /health/ready HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n' >&3 && grep -q '\"status\":\"UP\"' <&3"]
    interval: 30s
    timeout: 10s
    retries: 10
    start_period: 60s
```

### 2. Keycloak realm + client seed — `ticketing/auth/keycloak_setup.py`

Idempotent Python script using the `python-keycloak` library. Run once after
Keycloak starts. Must be safe to re-run (check-before-create everywhere).

**Add to `requirements.grm.txt`:**
```
python-keycloak>=3.9.0
```

**Script must configure:**

```
Realm:  grm
  ├── Client: ticketing-ui
  │     flow: standard (authorization_code + PKCE)
  │     redirectUris: http://localhost:3001/*, https://grm.stage.facets-ai.com/*, https://grm.facets-ai.com/*
  │     webOrigins: same
  │     access token lifespan: 3600s (1 hour)
  │     token mappers:
  │       • user attribute "grm_roles"      → JWT claim "custom:grm_roles"       (string)
  │       • user attribute "organization_id"→ JWT claim "custom:organization_id" (string)
  │       • user attribute "location_code"  → JWT claim "custom:location_code"   (string, optional)
  │       • standard: sub, email, name, email_verified
  └── Client: ticketing-api (confidential, for backend JWKS / service account)
        flow: client_credentials (backend-to-backend only)
```

**Also create demo officer accounts** (these replace the Cognito pool entries):

| username | grm_roles | organization_id |
|----------|-----------|-----------------|
| admin@grm.local | super_admin | DOR |
| l1-officer@grm.local | site_safeguards_focal_person | DOR |
| l2-piu@grm.local | pd_piu_safeguards_focal | DOR |
| grc-chair@grm.local | grc_chair | DOR |
| seah@grm.local | seah_national_officer | DOR |
| adb@grm.local | adb_hq_safeguards | ADB |

All with temporary password `GrmDemo2026!` and `requiredActions: ["UPDATE_PASSWORD"]`
so officers change it on first login.

**Run the script via:**
```bash
docker compose -f docker-compose.yml -f docker-compose.grm.yml exec ticketing_api \
  python -m ticketing.auth.keycloak_setup
```

### 3. Frontend — replace `CognitoAuthClient` with OIDC client

**Create `channels/ticketing-ui/lib/auth/oidc-auth.ts`** — a drop-in replacement
for `cognito-auth.ts` with the same public interface but targeting Keycloak endpoints.

Keycloak OIDC endpoints (given `KEYCLOAK_ISSUER = http://localhost:8080/realms/grm`):
```
Authorization: {issuer}/protocol/openid-connect/auth
Token:         {issuer}/protocol/openid-connect/token
Logout:        {issuer}/protocol/openid-connect/logout
JWKS:          {issuer}/protocol/openid-connect/certs
```

The existing `CognitoAuthClient` implements Authorization Code manually.
Keep the same pattern — same `getAuthorizationUrl()`, `handleCallback()`,
`getCurrentUser()`, `getAccessToken()`, `signOut()` interface. Only the
endpoint URLs change.

**Add PKCE support** (Keycloak best practice):
- Generate `code_verifier` (random 43–128 chars), store in sessionStorage
- Derive `code_challenge = base64url(sha256(verifier))`
- Add `code_challenge_method=S256&code_challenge={challenge}` to auth URL
- Send `code_verifier` in the token exchange body

**Update `AuthProvider.tsx`**: change `import { CognitoAuthClient }` →
`import { OIDCAuthClient }` and update constructor args to use new env vars.

The `MOCK_USER` constant and bypass mode remain unchanged.

**New env vars** (replace `NEXT_PUBLIC_COGNITO_*` in `.env.local`):
```bash
# Remove these:
# NEXT_PUBLIC_COGNITO_USER_POOL_ID=
# NEXT_PUBLIC_COGNITO_CLIENT_ID=
# NEXT_PUBLIC_COGNITO_DOMAIN=
# NEXT_PUBLIC_COGNITO_REGION=

# Add these:
NEXT_PUBLIC_OIDC_ISSUER=http://localhost:8080/realms/grm
NEXT_PUBLIC_OIDC_CLIENT_ID=ticketing-ui
NEXT_PUBLIC_REDIRECT_SIGN_IN=http://localhost:3001/auth/callback
NEXT_PUBLIC_REDIRECT_SIGN_OUT=http://localhost:3001/login
```

No client secret in the browser — Keycloak `ticketing-ui` client must be set
as **public** (not confidential). PKCE covers the security gap.

### 4. Backend — implement `get_current_user()` in `ticketing/api/dependencies.py`

The `INTEGRATION POINT` comment in the file already shows the exact structure.
Implement it using Keycloak's JWKS endpoint.

**Create `ticketing/auth/keycloak_jwt.py`:**

```python
"""
Verify JWTs issued by Keycloak using the realm's JWKS endpoint.
Caches keys for 5 minutes to avoid fetching on every request.
"""
import time
import httpx
from jose import jwt, JWTError
from ticketing.config.settings import get_settings

_jwks_cache: dict = {}
_cache_ts: float = 0.0
_CACHE_TTL = 300  # 5 minutes

def _get_jwks() -> dict:
    global _jwks_cache, _cache_ts
    if time.time() - _cache_ts < _CACHE_TTL:
        return _jwks_cache
    settings = get_settings()
    url = f"{settings.keycloak_issuer}/protocol/openid-connect/certs"
    resp = httpx.get(url, timeout=5.0)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _cache_ts = time.time()
    return _jwks_cache

def verify_keycloak_token(token: str) -> dict:
    """Decode and verify a Keycloak-issued JWT. Raises JWTError on failure."""
    settings = get_settings()
    jwks = _get_jwks()
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=settings.keycloak_client_id,
        issuer=settings.keycloak_issuer,
    )
```

**Add to `requirements.grm.txt`:**
```
python-jose[cryptography]>=3.3.0
```

**Update `dependencies.py`** — replace the stub:

```python
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from ticketing.auth.keycloak_jwt import verify_keycloak_token
from jose import JWTError

security = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_internal_user_id: str | None = Header(None),
    x_internal_role: str | None = Header(None),
) -> CurrentUser:
    settings = get_settings()

    # Dev bypass: if no Keycloak issuer configured, or x-internal headers present
    if not settings.keycloak_issuer or x_internal_user_id:
        return CurrentUser(
            user_id=x_internal_user_id or "mock-super-admin",
            role_keys=(x_internal_role or "super_admin").split(","),
            organization_id="DOR",
        )

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        claims = verify_keycloak_token(credentials.credentials)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    return CurrentUser(
        user_id=claims["sub"],
        role_keys=claims.get("custom:grm_roles", "").split(","),
        organization_id=claims.get("custom:organization_id", ""),
        location_code=claims.get("custom:location_code"),
    )
```

**Dev bypass logic:**
- If `KEYCLOAK_ISSUER` is empty in settings → return mock user (no Keycloak running)
- If `x-internal-user-id` header present → use it (existing pattern for internal calls)
- Otherwise → validate Bearer token against Keycloak

**New settings** (add to `ticketing/config/settings.py`):
```python
keycloak_issuer: str = ""          # http://keycloak:8080/realms/grm in Docker
keycloak_client_id: str = "ticketing-api"
keycloak_admin_url: str = ""       # http://keycloak:8080 for admin API
keycloak_admin_password: str = ""  # KEYCLOAK_ADMIN_PASSWORD
```

**New env vars** (add to `env.local`):
```bash
KEYCLOAK_ISSUER=http://keycloak:8080/realms/grm
KEYCLOAK_CLIENT_ID=ticketing-api
KEYCLOAK_ADMIN_URL=http://keycloak:8080
KEYCLOAK_ADMIN_PASSWORD=admin
```

### 5. Officer invite flow — `ticketing/api/routers/users.py`

Currently stubbed. Implement `POST /api/v1/users/invite` using Keycloak Admin API:

```python
from python_keycloak import KeycloakAdmin

def _keycloak_admin() -> KeycloakAdmin:
    settings = get_settings()
    return KeycloakAdmin(
        server_url=settings.keycloak_admin_url,
        username="admin",
        password=settings.keycloak_admin_password,
        realm_name="grm",
        verify=True,
    )

@router.post("/users/invite")
def invite_officer(body: OfficerInviteRequest, current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(403, "Admins only")
    
    kc = _keycloak_admin()
    kc.create_user({
        "username": body.email,
        "email": body.email,
        "enabled": True,
        "attributes": {
            "grm_roles": body.role_key,
            "organization_id": body.organization_id,
        },
        "credentials": [{
            "type": "password",
            "value": body.temp_password or "ChangeMe123!",
            "temporary": True,
        }],
        "requiredActions": ["UPDATE_PASSWORD", "VERIFY_EMAIL"],
    })
    # Keycloak sends the verification email automatically if SMTP is configured
    # For proto: return the temp password in the response so admin can share it
    return {"ok": True, "email": body.email, "message": "User created in Keycloak"}
```

Gracefully handle `409 Conflict` (user already exists) — return a clear error.

### 6. Migration guide — `docs/claude-tickets/AUTH_MIGRATION.md`

Document:
1. How to export existing Cognito users: `aws cognito-idp list-users --user-pool-id <id>`
2. How to import into Keycloak using `keycloak_setup.py`
3. Production hardening checklist:
   - Change `start-dev` → `start` in docker-compose
   - Set `KC_HOSTNAME`, `KC_HTTPS_CERTIFICATE_FILE`, `KC_HTTPS_CERTIFICATE_KEY_FILE`
   - Change default admin password
   - Configure SMTP for email verification
   - Set token lifespans (access: 1h, refresh: 8h, SSO session: 8h)
4. How to update redirect URIs when deploying to a new domain

---

## Hard Constraints

1. **DO NOT touch** `backend/`, `rasa_chatbot/`, `docker-compose.yml` — chatbot system
2. **New code lives ONLY in:**
   - `ticketing/auth/` (new module)
   - `ticketing/api/dependencies.py` (update existing)
   - `ticketing/api/routers/users.py` (update existing)
   - `ticketing/config/settings.py` (add fields)
   - `channels/ticketing-ui/lib/auth/oidc-auth.ts` (new, replaces cognito-auth.ts)
   - `channels/ticketing-ui/app/providers/AuthProvider.tsx` (update import only)
   - `docker-compose.grm.yml` (add Keycloak service)
   - `requirements.grm.txt` (add python-keycloak, python-jose)
3. **Keep dev bypass working**: `NEXT_PUBLIC_BYPASS_AUTH=true` skips OIDC entirely.
   `KEYCLOAK_ISSUER=""` in backend settings also bypasses JWT validation.
4. **Idempotent setup**: `keycloak_setup.py` must be re-runnable without errors
5. **Same Postgres**: use the existing `db` container, `keycloak` schema — no new DB
6. **Don't break the existing `x-internal-user-id` / `x-api-key` auth paths** —
   these are used by internal service-to-service calls (chatbot → ticketing)

---

## Deliverables Checklist

- [ ] `docker-compose.grm.yml` — Keycloak service added, healthcheck, depends_on
- [ ] `ticketing/auth/__init__.py`
- [ ] `ticketing/auth/keycloak_jwt.py` — JWKS fetch + JWT verify with 5-min cache
- [ ] `ticketing/auth/keycloak_setup.py` — realm/client/mappers/demo users (idempotent)
- [ ] `ticketing/api/dependencies.py` — `get_current_user()` wired to Keycloak
- [ ] `ticketing/api/routers/users.py` — `POST /users/invite` via Keycloak Admin API
- [ ] `ticketing/config/settings.py` — `keycloak_*` fields added
- [ ] `channels/ticketing-ui/lib/auth/oidc-auth.ts` — PKCE-enabled OIDC client
- [ ] `channels/ticketing-ui/app/providers/AuthProvider.tsx` — import swapped
- [ ] `channels/ticketing-ui/.env.local` — COGNITO vars replaced with OIDC vars
- [ ] `requirements.grm.txt` — `python-keycloak>=3.9.0`, `python-jose[cryptography]>=3.3.0`
- [ ] `docs/claude-tickets/AUTH_MIGRATION.md` — Cognito → Keycloak migration guide

---

## Verification Tests

After implementation, run these in order:

```bash
# 1. Keycloak health
curl http://localhost:8080/realms/grm/.well-known/openid-configuration | python3 -m json.tool | grep issuer

# 2. Run realm setup
docker compose -f docker-compose.yml -f docker-compose.grm.yml exec ticketing_api \
  python -m ticketing.auth.keycloak_setup

# 3. Backend dev bypass still works (no KEYCLOAK_ISSUER set)
curl http://localhost:5002/api/v1/tickets -H 'x-internal-user-id: mock-super-admin' -H 'x-internal-role: super_admin' | python3 -m json.tool | head -5

# 4. Get a real token from Keycloak and hit the API
TOKEN=$(curl -s -X POST http://localhost:8080/realms/grm/protocol/openid-connect/token \
  -d "client_id=ticketing-ui&grant_type=password&username=admin@grm.local&password=GrmDemo2026!" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl http://localhost:5002/api/v1/tickets -H "Authorization: Bearer $TOKEN" | head -5

# 5. Frontend bypass mode
# Open http://localhost:3001 — should load with NEXT_PUBLIC_BYPASS_AUTH=true without Keycloak

# 6. Invite a new officer
curl -X POST http://localhost:5002/api/v1/users/invite \
  -H 'Content-Type: application/json' -H 'x-internal-user-id: mock-super-admin' -H 'x-internal-role: super_admin' \
  -d '{"email":"newtest@grm.local","role_key":"grc_member","organization_id":"DOR"}'
```

All 6 checks must pass before committing.

---

## Notes on Production Hardening (post-demo)

These are out of scope for this task but document them in `AUTH_MIGRATION.md`:

- Switch `start-dev` → `start` in Keycloak Docker command
- Set `KC_HOSTNAME=grm.facets-ai.com` (or behind reverse proxy with `KC_PROXY=edge`)
- Configure SMTP (`KC_SMTP_*`) for email verification and password reset
- Rotate `KEYCLOAK_ADMIN_PASSWORD` — store in AWS Secrets Manager or equivalent
- Enable brute force protection in Keycloak realm settings
- Set refresh token rotation + revocation on logout
- For multi-country: consider one Keycloak instance with multiple realms (one per country)
  or a single `grm` realm with organization attributes per user
