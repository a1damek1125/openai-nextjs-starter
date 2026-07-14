# Action & Communication Engine — Upload Link Generator

> **Ground truth**: `finalis/actions/services.py::UploadLinkGenerator`,
> `finalis/actions/models.py::UploadLink`, engine step 7
> (`UPLOAD_ACTIONS`). Tests:
> `tests/test_action_communication.py::test_11_expiring_link_lifecycle`,
> `test_17_e2e_missing_photo_followup`, `test_7`. Spec: doc 04
> (documents/photos), doc 22 §Documents (`POST /uploads` presigned flow),
> doc 47 (OCR engine).

## 1. Token handling as coded — hash only, never the raw token

```python
token = secrets.token_urlsafe(24)                       # CSPRNG, ~32 url-safe chars
link  = UploadLink(..., token_hash=UploadLink.hash_token(token), ...)
url   = f"https://upload.finalis.example/u/{token}"
```

- Token generated with **`secrets.token_urlsafe(24)`** (cryptographically
  secure, unguessable).
- Only the **SHA-256 hash** is stored on the entity
  (`hashlib.sha256(token.encode()).hexdigest()`); lookups re-hash the
  presented token (`self.links[UploadLink.hash_token(token)]`). **The raw
  token is never persisted** — a database leak does not leak usable links.
  (Scaffold caveat: the generator's `_urls` id→URL map exists purely so
  tests can recover the link; production must not keep it — see
  `data-model.md` §3.)
- Default TTL **72h** (`ttl_hours: int = 72`; `expires_at = now + ttl`).
- Creation is audited: `UPLOAD_LINK_CREATED` (payload: `link_id`, `purpose`,
  `expires_at` — not the token).

## 2. State machine

```
CREATED → SENT → OPENED → USED
              ↘ EXPIRED (TTL passed at open/use time)
              ↘ REVOKED (manual revoke(link_id))
```

As coded (`open` / `use` / `revoke`):

- `open(token, now)`: unknown hash → `None`; past `expires_at` or already
  `EXPIRED`/`REVOKED` → marks/keeps `EXPIRED`, returns `None`; from
  `CREATED`/`SENT` → sets `OPENED` + audits `UPLOAD_LINK_OPENED`
  (`actor="client"`).
- `use(token, now, mime=…, size_mb=…)`: re-runs `open` (so expiry is
  enforced on every use), then rejects `mime not in allowed_types` or
  `size_mb > max_size_mb` (returns `False`; the link stays `OPENED` — a bad
  file does not burn the link); on success sets `USED`, stamps `used_at`,
  audits `UPLOAD_LINK_USED` (payload includes `mime`).
- `revoke(link_id)`: sets `REVOKED`; a revoked link can never be opened.
- Honest gap: `SENT` is in the enum but no code path sets it — the engine
  creates the link and embeds the URL in the draft, and nothing flips
  `CREATED → SENT` when `MESSAGE_SENT` fires. One-line production fix.

**Tested** in `test_11_expiring_link_lifecycle`: create → open (+1h) → use
(`image/jpeg`, 4 MB) → `USED`; a 1h-TTL link opened a day later → `None` and
`EXPIRED`; `application/x-msdownload` upload → refused.

## 3. Allowed types and size cap

Defaults on the entity: `allowed_types = ("image/jpeg", "image/png",
"application/pdf")`, `max_size_mb = 25`. These are the **only** content
checks coded today. The **malware-scan hook is Designed, not coded** — there
is no scan call in `use()`; production inserts AV scanning before the upload
is accepted (§5).

## 4. Engine wiring and the tested E2E flow

Engine step 7: for `UPLOAD_ACTIONS = {send_photo_request,
send_document_request, send_upload_link}` the engine creates a link
(`purpose` from the request payload, default `installation_photo`) and
injects the URL as the `upload_link` template variable, so the composed
message carries it (`test_7_missing_photo_message_polish_with_link`).

**E2E scenario 1** (`test_17_e2e_missing_photo_followup`), the full
upload → case-unblocked loop:

1. `send_photo_request` executes → `out.upload_url` present and embedded in
   `draft.final_text`.
2. Delivery confirmed (`record_delivery(status="delivered")`).
3. Client opens the link (+3h) and uploads `image/jpeg`, 3.2 MB (+4h) →
   link `USED`.
4. `MissingInfoService.resolve(case, "installation_photo", audit,
   source="upload")` marks the blocking `MissingItem` received — **the case
   is unblocked**; only `address` remains missing.
5. Full audit sequence asserted: `ACTION_REQUESTED → UPLOAD_LINK_CREATED →
   MESSAGE_DRAFT_CREATED → MESSAGE_SENT → MESSAGE_DELIVERED →
   UPLOAD_LINK_OPENED → UPLOAD_LINK_USED → MISSING_INFO_RESOLVED`, and
   `audit.verify_chain()` passes.

(In the scaffold, step 4 is invoked by the test standing in for the upload
service; production wires the upload completion event to the resolver.)

## 5. Production plan

- **Tenant-scoped upload service**: token resolved to `(tenant_id, case_id,
  purpose)` server-side; RLS-scoped storage paths; per-link rate limiting on
  the public endpoint.
- **S3 presigned PUT**: the upload page exchanges the (validated,
  non-expired) token for a short-lived presigned S3 PUT (doc 22
  `POST /uploads` flow) — file bytes never transit the Finalis API.
- **AV scan**: object-created event → antivirus scan (e.g. ClamAV lambda);
  quarantine on detection, only clean files proceed — this is the coded
  placeholder's real implementation.
- **Document ingestion into the OCR router**: clean upload → `Document/Photo`
  row → `document.received` event → the doc-47 OCR router pipeline
  (classification, extraction, confidence) → `missing_item.satisfied` /
  `MissingInfoService.resolve`, closing the same loop the E2E test proves
  with the mock.
