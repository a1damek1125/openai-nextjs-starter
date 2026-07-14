#!/usr/bin/env bash
# Finalis local dev setup — no external credentials required.
set -e
pip install fastapi uvicorn httpx playwright pytest
cp -n .env.example .env 2>/dev/null || true
echo "Setup done. Run:"
echo "  python3 -m finalis.portal.serve      # backend+UI on :8000 (seeds demo)"
echo "  python3 -m pytest tests/ -q          # all tests incl. browser E2E"
echo "Login: owner@demo.finalis / demo1234"
