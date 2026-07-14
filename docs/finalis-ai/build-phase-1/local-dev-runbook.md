# Finalis — Local Dev Runbook (no external credentials needed)

## Setup (once)
```bash
bash scripts/dev_setup.sh          # installs fastapi/uvicorn/httpx/playwright/pytest
cp .env.example .env               # optional; defaults work
```

## Run
```bash
python3 -m finalis.portal.serve            # http://127.0.0.1:8000
# custom db/port: python3 -m finalis.portal.serve mydb.db 8080
```
Seeds the demo tenant on first run. **Login: owner@demo.finalis / demo1234**
(also manager@ / operator@ / viewer@; isolation tenant: owner@other.finalis).

## Test
```bash
python3 -m pytest tests/ -q                     # 346 tests, all local
python3 -m pytest tests/test_browser_e2e.py     # browser E2E (Chromium)
python3 -m pytest tests/test_local_demo_flow.py # founder demo flow
```

## Database
- **Local: SQLite** (Implemented and tested; file `finalis-dev.db`, versioned
  migrations v1–v2, idempotent, restart-survivable audit chain in SQL).
- **PostgreSQL: Scaffolded** — `docker-compose up postgres` provisions it;
  the driver swap is the documented next step. Docker was not exercisable in
  the build environment, so compose is provided but UNVERIFIED here.

## What is mock vs real (honest)
- Real: persistence, migrations, auth (PBKDF2+HMAC), RBAC, tenant isolation,
  REST APIs, portal UI calling APIs, audit hash chain, lifecycle kernel,
  telephony call-control logic, upload links, anti-spam/anti-harassment.
- **Mock (behind real interfaces, clearly marked `is_mock`)**: WhatsApp/SMS/
  email delivery, Chatwoot, Temporal scheduling, telephony provider,
  invoice/payment/fulfillment providers, OCR/ASR/TTS engines.
- Awaiting credentials (after Adam returns): Meta WhatsApp Cloud, Twilio,
  SMTP, Chatwoot instance, Temporal cluster, S3/MinIO, billing provider,
  LiveKit SIP trunk + phone number.
