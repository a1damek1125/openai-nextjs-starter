# FINALIS Trusted Evaluation Kernel — Specification (SP0011)

The Trusted Evaluation Kernel (TEK) is the small, trusted checker set the whole
Finalis-1000 score depends on. It does NOT generate scenarios, run agents, or
judge — it **checks certificates** produced by the untrusted stack (D-0011-006).

## Trusted Computing Base (explicit + minimized)

**TCB members** (`docs/evaluation/FINALIS_EVALUATION_TCB_MANIFEST.json`, content-
hashed — trust pinned to exact bytes): `canon.py`, `model.py`, `kernel.py`,
`credits.py`, `hardgates.py`, `score.py`, `genome.py`, `admit.py`, `freeze.py`,
`configuration.py`.

**Minimal Trusted Kernel** (irreducible core): `canon.py` (hashing), `model.py`
(vocabularies + maturity + accounting), `kernel.py` + `credits.py` (the
independent checker), `hardgates.py` + `score.py` (the gate + arithmetic).

**Untrusted, re-checked** (deliberately OUTSIDE the TCB): `scenarios.py`,
`oracles.py`, `judges.py`, `statistics.py`, `robust.py`, `longhorizon.py`,
`causal.py`, `calibration.py`, `invariance.py`, `providers.py`, `fidelity.py`,
`drift.py`, `coverage.py`, `contamination.py`, `claims.py`. Their output is a
certificate or a diagnostic — never a credit — until the TEK accepts it. The
kernel is materially smaller than the stack it checks.

## What the kernel checks

Per awarded credit (`credits.check_certificate`, `kernel.check_credits`):

1. certificate schema + hash recomputes (no tampering);
2. configuration root matches the evaluated configuration;
3. Program Seal matches the admitted SP0010 seal;
4. achieved maturity ≥ required maturity (independently re-derived, never trusted
   from the issuer's self-report);
5. every declared hard-gate result is PASS;
6. evidence present, current, unrefuted; support references non-empty;
7. no blocking defeater;
8. obligations re-derived by the checker AGREE with the certificate's self-report
   (a certificate that lies about its own obligations is rejected).

Then, over the whole scorecard (`kernel.verify_all`): score arithmetic (Σ awarded
× 5 ≤ 1000; official total zeroed when the hard gate blocks), genome recomputation
(`genome.verify_genome`), and seal binding (`genome.verify_seal` — repository
commit, hash, and grants_runtime_authority=False).

## Determinism + identity

The kernel is deterministic (same inputs → same verdict) and its identity is the
content hash of `kernel.py`, `credits.py`, `score.py`, `genome.py`, `hardgates.py`,
`canon.py`, `model.py` (`kernel.kernel_identity`) — kernel substitution moves the
root and is detectable. The kernel opens no external effect and never imports
product code (`boundary.check_boundary` returns empty).

## The gate property

A solver/generator/judge verdict WITHOUT a valid, independently-checked
certificate can never award a credit. This is the SP0011 analogue of the SP0010
proof-carrying discipline: **trust the checker, not the solver.**
