#!/usr/bin/env bash
# Print cryptographically strong values for production secrets.
# Paste into apps/api/.env.production — never commit that file.
set -euo pipefail

echo "=== Recall production secret generators ==="
echo
echo "JWT_SECRET=$(openssl rand -base64 32 | tr -d '\n')"
echo "OAUTH_TOKEN_ENCRYPTION_KEY=$(cd "$(dirname "$0")/../apps/api" && uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"
echo "REVENUECAT_WEBHOOK_AUTH=$(openssl rand -hex 32)"
echo
echo "Copy the lines above into apps/api/.env.production"
echo "Then fill DATABASE_URL, REDIS_URL, GOOGLE_*, OPENROUTER_API_KEY, R2_*, CORS_ORIGINS."
