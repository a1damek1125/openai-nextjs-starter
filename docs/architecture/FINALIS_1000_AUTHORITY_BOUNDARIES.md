# FINALIS 1000 — AUTHORITY BOUNDARIES

**SP0000 · docs-only.** Baseline HEAD `5c30c60`. This document locks *where authority lives* and *where it does not*. It is the constitution's core: every other layer inherits these rules.

## The authority ladder (locked)

Each `≠` is a hard wall. Crossing it silently is a P0 architecture violation.

```
DATA                 ≠  CLAIM
CLAIM                ≠  VERIFIED FACT
VERIFIED FACT        ≠  AUTHORITY
CERTIFIED CONCLUSION ≠  AUTHORITY            (LGGT+ certifies; it does not authorize)
RECOMMENDATION       ≠  AUTHORITY
MODEL OUTPUT         ≠  AUTHORITY
APPROVAL ARTIFACT    ≠  UNLIMITED EXECUTION RIGHT
```

**Authority lives only inside the Finalis governance chain** — the existing and future proof-carrying ladder (CORE-A1..A6 → TOOL-B1..B9.2 → EMP-A1 → future L1/L8 governance). Authority narrows down the ladder and never widens (verified pattern: B8 cannot activate B9; B9.1 recovery creates no authority/effect; B9.2 PoWO authorizes nothing; EMP-A1 admits + prepares a fenced handoff, executes nothing).

## The five roles (locked separation — D-0000-11)

| Role | May… | May NOT… |
|---|---|---|
| **Generative Intelligence** | understand, draft, converse | authorize, execute, define state |
| **Adaptive Intelligence** | predict, optimize, rank | authorize, execute |
| **Certified Intelligence (LGGT+)** | certify formalizable conclusions vs versioned facts/rules/snapshot | authorize, execute, assert world-truth, be the conversational brain |
| **Governance Intelligence** | authorize, apply policy, grant capability | generate content, execute the effect itself |
| **Effector** | execute a granted capability against a tool/provider/sandbox | decide whether it *should* run |
| **Outcome Observer** | observe effect vs intended outcome | authorize, mutate authoritative state directly |
| **Learning** | propose candidate improvements | self-promote to production |

## Per-actor authority matrix

| Actor | Trust | May provide data? | May provide authority? | May execute? | May mutate memory? | May create external effect? |
|---|---|---|---|---|---|---|
| User (in role) | conditionally trusted | yes | via governance only | no | via governed path | via governance only |
| Tenant admin | conditionally trusted | yes | scoped by RBAC | no | governed | governed |
| **Model output** | untrusted-as-authority | yes (as draft) | **NEVER** (INV-0000-02) | no | no (proposes only) | no |
| **External content** (email/doc/web/tool/MCP/A2A/voice) | untrusted | yes (as data) | **NEVER** (INV-0000-03, D-0000-12) | no | only via admission | no |
| **LGGT+ certification** | trusted-as-certificate | yes (certified conclusion) | **NEVER as execution** (INV-0000-04) | no | no | no |
| **Frontend / portal** | not authoritative | presents | **NEVER** (INV-0000-05) | no | no (calls governed APIs) | no |
| Provider / sandbox | external trust domain | yes (effect result) | no | yes (granted capability only) | no | yes, post-governance |
| MCP server | external trust domain | yes (as data) | no | no (adapter) | no | no |
| A2A agent | external trust domain | yes (as data) | no | no | no | no |
| Learning pipeline | gated | candidate lessons | no | no | via promotion gate only | no |
| **Finalis governance chain** | authoritative | — | **yes (sole source)** | grants capability | governs | authorizes |

## Load-bearing invariants (cross-ref `FINALIS_1000_MASTER_ARCHITECTURE_LOCK.md §INVARIANTS`)

- INV-0000-02 Model output is never authority.
- INV-0000-03 External content is never authority.
- INV-0000-04 LGGT certification is not execution authority.
- INV-0000-05 Frontend is not business authority.
- INV-0000-06 One user-facing employee may use many internal specialists, but Owned Work has **one** authoritative ownership model.
- INV-0000-10 Real external effects must pass Finalis governance.
- INV-0000-13 **Tenant scope is absolute and binds every layer** — Owned Work, memory, KB snapshots, learning candidates/promotions, events, model calls, and effects are tenant-scoped; no memory or learning may cross tenants without an explicit governed, anonymized path.
- INV-0000-14 **Human intervention/override/stop control must exist at every capability-grant and effect boundary** (structural Art. 14-style oversight for high-risk actions).

## Why these walls exist (red-team-anchored)

- **Prompt/context/memory poisoning** → if model output or external content could confer authority, a poisoned input becomes an instruction to act. The wall makes poisoning a *data* problem (contained at admission), never an *authority* problem.
- **Artifact-as-authority** → an approval artifact is a bounded, consumable grant, not an unlimited execution right (matches B7/B8/EMP-A1 fencing). Prevents replay of an old approval into a new effect.
- **Provider irreplaceability** → no provider owns business truth, so any provider can be swapped without rebuilding the core (INV-0000-09).
- **Second source of truth** → the new portal presents; it never re-owns CRM/Evidence/Case/CPQ/governance (D-0000-15, INV-0000-07).
