# FINALIS 1000 — Architecture Guard Rules (SP0001)

The Architecture Immune System is deterministic, repository-local tooling under
`tools/architecture/`. It **inspects** product code; product code must **never
import it** (INV-0001-09). Stdlib only — OPA/Rego, CodeQL, Tree-sitter stay
behind `ScannerAdapter` boundaries (D-0001-15/16).

## Commands (`python -m tools.architecture <cmd>`)

| Command | Purpose | Exit 1 when |
|---|---|---|
| `validate` | Full-repo conformance gate (declared twin vs observed) | any P0/P1 or twin-invalid |
| `diff [--base <c>] [--intent f.json]` | Diff-aware delta vs declared baseline + intent classification | P0/P1 or undeclared drift |
| `impact --capability <id[,id]>` | Change Impact Cone (reverse reachability) | never (advisory) |
| `context --capability <id>` | Agent Context Spine for one capability | unknown capability |
| `duplication [--threshold t]` | Semantic duplication candidates (advisory) | never |
| `drift` | Drift Observatory snapshot vector | never |
| `attest [--base <c>] [--intent f]` | Proof-Carrying Change Envelope (deterministic, unsigned) | architecture invalid |

All accept `--json` and `--now YYYY-MM-DD` (deterministic waiver-expiry clock).

## Hard gates (P0/P1 — block; INV-0001-06)

| Finding | Severity | Rule |
|---|---|---|
| `FORBIDDEN_DEPENDENCY` | P0 | A capability imports a module matching its `forbidden_dependencies` (e.g. a product engine importing `finalis.ai_employee`). Transitive edges counted. |
| `CAPABILITY_OWNERSHIP_CONFLICT` | P0 | Two capabilities claim the same module, route namespace, or table namespace (INV-0001-01). |
| `MIGRATION_MUTATION` | P0 | A historical migration digest changed or a version was removed/renumbered (INV-0001-05 / append-only). Non-contiguous append → P1. |
| `EFFECT_GATE_VIOLATION` | P0 | A network primitive (`requests`/`httpx`/`smtplib`/`socket`/`urllib.request`/`http.client`/…) appears in non-test product code while `real_external_effects_allowed=false` (INV-0001-10). |
| `UNOWNED_NODE` | P1 | A product module has no canonical owner. |
| `ARCHITECTURE_DEPENDENCY_CYCLE` (in `acyclic_required` scope) | P1 | A cycle inside a sub-graph the twin declares must be acyclic. |
| `SCAN_ERROR` / `UNSUPPORTED_LANGUAGE_ARCHITECTURE_SCAN` | P1 | A file that must be scanned cannot be parsed / a foreign language has no `ScannerAdapter` (fail-closed, §17.2/§18.1). |
| `WAIVER_EXPIRED` | P1 | An `ACTIVE` waiver relied upon has passed its `expires_at`. |

## Advisory signals (P2 — never block on their own; D-0001-09)

`ARCHITECTURE_DEPENDENCY_CYCLE` (general, outside acyclic-required scope) ·
`DYNAMIC_IMPORT_ADVISORY` (new dynamic import) · `SPEC_CODE_DRIFT_DETECTED`
(missing spec anchor) · `DUPLICATION_CANDIDATE`. These feed the Drift Observatory
and review scope; a score can **never** override a P0/P1 (INV-0001-07/14).

## Effect-gate limitation honesty (§17.3 — do not overclaim)

Static scanning **cannot mathematically prove the absence of all network
behaviour.** The effect gate is sound for its stated scope and honest about the
rest:

- **Caught as P0** (hard): a static network-primitive import — `requests`,
  `httpx`, `aiohttp`, `smtplib`, `socket`, `urllib.request`, `http.client`,
  `ftplib`, `boto3`, `paramiko`, `websocket(s)` — anywhere in non-test product
  code, including inside functions (`ast.walk` reaches nested imports).
- **Caught as P2** (advisory, cannot be *proven* to be egress): dynamically
  constructed imports — `__import__(...)`, `importlib.import_module(...)` — and
  shell-outs — `subprocess.{run,Popen,call,check_output,check_call}`,
  `os.system`, `os.popen` — which could reach the network via `curl`/`wget` but
  cannot be confirmed statically.
- **Not detectable by this static gate** (disclosed blind spot): egress hidden
  behind fully computed strings, C extensions, eval, or a compromised
  dependency. The complete effect assurance therefore **combines** the static
  scan with the runtime no-external-effect tests already in the governance
  kernel (B9/B9.2), the provider registry, and route topology — it is not the
  static gate alone. A future `ScannerAdapter` (CodeQL data-flow) can narrow the
  P2 band; the honest posture until then is *advisory + runtime cross-check*, not
  a false claim of completeness.

## Change Intent (D-0001-03/04)

An architecture-significant change declares intent (`FINALIS_1000_CHANGE_INTENT_SCHEMA.json`):
target capabilities, change type, expected paths/routes/tables/dependency/effect
changes. `diff --intent` classifies each delta as declared or
`UNDECLARED_ARCHITECTURE_DRIFT`. **Intent is not authority** — it cannot waive a
hard invariant (a `waives` entry naming `bypass_tenant_isolation`,
`open_effect_gate`, `mutate_historical_migration`, … is rejected).

## Waivers (§13.2)

`PROPOSED → ACTIVE → EXPIRED` (or `REJECTED`/`REVOKED`). No permanent anonymous
waiver: `owner`, `reason`, `expires_at` (≤ 90 days) required. Scope strings match
finding signatures. Waived P0/P1 are suppressed only while the waiver is active.

## Determinism (INV-0001-12)

Same repository tree + same manifest ⇒ same findings + same proof-envelope hash.
No wall-clock in any hashed core (`--now` is injected). The Proof Envelope is
**evidence, not authority** (INV-0001-08); it is unsigned (no KMS yet, D-0001-14).

## Regenerating the declared twin

`python -m tools.architecture.bootstrap --write` renders
`FINALIS_1000_ARCHITECTURE_TWIN.json` from `capabilities.py` + the observed
baseline. This is **offline seeding** (§5.2) — never part of the gate path.
