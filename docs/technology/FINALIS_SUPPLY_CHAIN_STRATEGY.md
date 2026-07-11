# FINALIS Supply-Chain & BOM Strategy (SP0004 D-0004-77/78/79)

SP0004 defines **strategy only** — it does not implement a production SBOM
pipeline and makes **no compliance claim without implementation evidence**
(D-0004-77, AC-0004-129).

| Standard | Decision | Target | Notes |
|---|---|---|---|
| SLSA | ADOPT_TARGET | v1.2 | future build-provenance target; approved spec line |
| CycloneDX | ADOPT_TARGET | 1.7 | SBOM + AI/ML-BOM (ML-BOM since 1.6) |
| SPDX | EVALUATE | 3.0.1 | complementary; 3.1 is a release candidate |
| AI/ML-BOM | ADOPT_TARGET | CycloneDX 1.7 | model/adapter/eval inventory strategy |

No unnecessary proprietary BOM format is introduced (AC-0004-133). An attestation
is a **claim requiring verification**, distinct from verification itself — a
verification policy must inspect it (D-0004-79, AC-0004-134).
