# Nginx location blocks for GRM on staging EC2

Add these server blocks to the existing Nginx config on the EC2.
The existing chatbot config is at `deployment/nginx/webchat_rest_docker.conf`.
Create a new file: `deployment/nginx/grm.conf`

---

## grm.stage.facets-ai.com

```nginx
server {
    listen 80;
    server_name grm.stage.facets-ai.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name grm.stage.facets-ai.com;

    ssl_certificate     /etc/letsencrypt/live/grm.stage.facets-ai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/grm.stage.facets-ai.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Next.js UI
    location / {
        proxy_pass         http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Ticketing API — proxied under /api/v1/ so the UI can call it same-origin
    # (avoids CORS for production; keep CORS middleware in FastAPI as fallback)
    location /api/v1/ {
        proxy_pass         http://localhost:5002/api/v1/;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

---

## Steps on EC2

```bash
# 1. Issue certificate (if not already done)
certbot certonly --nginx -d grm.stage.facets-ai.com

# 2. Create config file
sudo nano /etc/nginx/conf.d/grm.conf
# paste the server block above

# 3. Test + reload
sudo nginx -t && sudo nginx -s reload

# 4. Start GRM stack
cd /home/ubuntu/nepal_chatbot_claude
docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d

# 5. Run migration + seed (first deploy only)
docker compose -f docker-compose.yml -f docker-compose.grm.yml \
  --profile grm-init run --rm grm_migrate
docker compose -f docker-compose.yml -f docker-compose.grm.yml \
  --profile grm-init run --rm grm_seed
```

---

## Environment variables needed on EC2

Add to `/home/ubuntu/nepal_chatbot_claude/env.local` on the staging server:

```env
TICKETING_PORT=5002
TICKETING_SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_urlsafe(32))">

# Cognito (once pool is provisioned)
NEXT_PUBLIC_BYPASS_AUTH=false
NEXT_PUBLIC_COGNITO_DOMAIN=https://grm-ticketing.auth.ap-southeast-1.amazoncognito.com
NEXT_PUBLIC_COGNITO_CLIENT_ID=<from AWS console>
NEXT_PUBLIC_COGNITO_REGION=ap-southeast-1
NEXT_PUBLIC_REDIRECT_SIGN_IN=https://grm.stage.facets-ai.com/auth/callback
NEXT_PUBLIC_REDIRECT_SIGN_OUT=https://grm.stage.facets-ai.com/login

# Public URLs (browser-accessible)
NEXT_PUBLIC_API_URL=https://grm.stage.facets-ai.com/api/v1
NEXT_PUBLIC_BACKEND_API_URL=http://localhost:5001
```

---

## Proto shortcut (demo only — no Cognito)

For the May 10 demo, bypass auth completely:

```env
NEXT_PUBLIC_BYPASS_AUTH=true
NEXT_PUBLIC_API_URL=https://grm.stage.facets-ai.com
```

This logs everyone in as `mock-super-admin` with full access including SEAH.
