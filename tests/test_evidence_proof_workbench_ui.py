"""V-F static UI checks — the Evidence Proof Workbench is served, calls the
tested Evidence V-A..V-E APIs, exposes every proof panel (or an honest
MISSING label where no server API exists), and carries the mandated proof /
honesty labels. Browser behaviour, if any, lives in test_browser_e2e.py."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def page():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app).get("/portal").text


@pytest.fixture()
def norm(page):
    return " ".join(page.split())          # collapse HTML line wrapping


class TestWorkbenchPanelsExist:
    def test_1_workbench_section_exists(self, page):
        assert 'id="workbench-section"' in page
        assert "Evidence Proof Workbench" in page

    def test_2_dashboard_exists(self, page):
        assert 'id="wb-dashboard"' in page
        assert "Evidence Proof Dashboard" in page

    def test_3_evidence_list_exists(self, page):
        assert 'id="wb-list"' in page
        assert "Evidence List" in page

    def test_4_detail_panel_exists(self, page):
        assert 'id="wb-p-detail"' in page and 'id="wb-detail-body"' in page
        assert "Evidence Detail" in page

    def test_5_merkle_inclusion_panel_exists(self, page):
        assert 'id="wb-p-inclusion"' in page
        assert "Merkle Inclusion Proof" in page

    def test_6_merkle_consistency_panel_or_missing(self, page):
        assert 'id="wb-p-consistency"' in page
        assert "Merkle Consistency / Append-Only" in page

    def test_7_proof_algebra_panel_exists(self, page):
        assert 'id="wb-p-algebra"' in page
        assert "Proof Algebra / Verdict" in page

    def test_8_state_machine_panel_exists(self, page):
        assert 'id="wb-p-state"' in page
        assert "Verification State Machine" in page

    def test_9_derivative_panel_exists(self, page):
        assert 'id="wb-p-derivative"' in page
        assert "Derivative Evidence Chain" in page

    def test_10_contract_history_panel_exists(self, page):
        assert 'id="wb-p-contract"' in page
        assert "Contract History / Decision Evidence" in page

    def test_11_provenance_panel_or_missing(self, norm):
        assert "Provenance / C2PA Signal" in norm
        assert "no provenance/C2PA API is exposed" in norm  # honest MISSING

    def test_12_timestamp_panel_or_missing(self, norm):
        assert "Timestamp / Evidence Record" in norm
        assert "No timestamp API is exposed" in norm

    def test_13_scitt_panel_or_missing(self, norm):
        assert "SCITT / Statement Receipt Readiness" in norm
        assert "SCITT statement/receipt integration is not implemented." \
            in norm

    def test_14_crypto_agility_panel_or_missing(self, page):
        assert 'id="wb-p-crypto"' in page
        assert "Cryptographic Agility / PQC Readiness" in page

    def test_15_conflict_matrix_panel_exists(self, page):
        assert 'id="wb-p-conflict"' in page
        assert "Evidence Conflict Matrix" in page

    def test_16_proof_explanation_panel_exists(self, page):
        assert 'id="wb-p-report"' in page
        assert "Proof Explanation / Human Report" in page

    def test_17_chain_graph_panel_exists(self, page):
        assert 'id="wb-p-graph"' in page
        assert "Evidence Chain Graph / Relationship" in page

    def test_18_production_honesty_panel_exists(self, page):
        assert 'id="wb-p-honesty"' in page
        assert "Production Honesty" in page


class TestMandatedProofMessages:
    MESSAGES = [
        # 19..43 from the mission's required-strings list.
        "NON-AUTHORITATIVE UI SUMMARY — server-side Evidence verification "
        "remains the source of truth.",
        "Positive signals cannot average away a critical proof failure.",
        "Integrity verification and business truth are separate verdicts.",
        "Merkle proof explains inclusion. It does not explain business "
        "truth.",
        "Hash match proves byte-level consistency, not customer intent.",
        "Cryptographic integrity is not the same as legal validity.",
        "Provenance is a signal, not final truth.",
        "C2PA provenance is not final truth.",
        "Timestamping proves existence at a time; it does not prove "
        "business truth.",
        "SCITT receipt presence does not equal business truth.",
        "Hash mismatch blocks automation.",
        "Derivative evidence must preserve parent linkage.",
        "A derivative is not stronger than its parent evidence.",
        "Contract history is append-oriented.",
        "Unknown or deprecated algorithms require review.",
        "External notarization is not connected.",
        "Blockchain anchoring is not implemented.",
        "RFC 3161 timestamp provider is not connected unless explicitly "
        "configured.",
        "RFC 4998 evidence record renewal is not implemented unless server "
        "exposes it.",
        "SCITT statement/receipt integration is not implemented.",
        "Sigstore/Rekor integration is not implemented.",
        "Post-quantum cryptography is not implemented in V-F.",
        "OCR router is not part of V-F.",
        "Payment/quote acceptance wiring is not part of V-F.",
        "Production readiness is false.",
    ]

    @pytest.mark.parametrize("msg", MESSAGES)
    def test_message_present(self, norm, msg):
        assert msg in norm, msg


class TestWorkbenchUsesRealApis:
    def test_calls_tested_evidence_apis(self, page):
        # Every data source is a real Evidence endpoint (no invented paths).
        for endpoint in ["'/evidence'", "/evidence/' + id",
                         "/chain", "/derivatives", "/contracts",
                         "/merkle-proof", "/evidence/merkle-roots",
                         "/immutability", "/verify"]:
            assert endpoint in page, endpoint

    def test_44_no_hardcoded_fake_evidence_rows(self, page):
        assert "Loading evidence…" in page          # list is API-driven
        assert "get('/evidence'" in page
        # No baked-in evidence identities/filenames standing in for the API.
        for fake in ("faktura-fake", "evidence-0001", "seed-evidence-id",
                     "example.com/evidence"):
            assert fake not in page, fake

    def test_45_escape_before_render_for_metadata(self, page):
        # Untrusted evidence metadata renders through esc() only.
        for escaped in ["esc(d.original_filename", "esc(r.original_filename",
                        "esc(d.id)", "esc(hashV", "esc(r.evidence_type)",
                        "esc(d.evidence_type)"]:
            assert escaped in page, escaped


class TestServerAuthorityLabels:
    def test_server_remains_authoritative(self, norm):
        for label in ("server-side Evidence verification remains the source "
                      "of truth",
                      "Server-side Evidence logic remains authoritative.",
                      "a display score cannot unlock actions",
                      "Verification state is server-authoritative.",
                      "Failed proof blocks automation."):
            assert label in norm, label

    def test_verdict_lattice_and_dimensions_present(self, page):
        # The proof-algebra dimensions and verdict lattice are exposed.
        for dim in ("HashIntegrity", "MerkleInclusion", "MerkleConsistency",
                    "DerivativeChain", "TenantIsolation", "AlgorithmAgility",
                    "BusinessContext"):
            assert dim in page, dim
        for verdict in ("VERIFIED_FOR_INTEGRITY", "VERIFIED_WITH_LIMITATIONS",
                        "REVIEW_REQUIRED", "FAILED_VERIFICATION",
                        "TAMPER_WARNING", "NOT_VERIFIED"):
            assert verdict in page, verdict


class TestMerkleConsistencyD3Integration:
    """EVIDENCE-MERKLE-C1: V-F D3 now shows server-verified consistency."""

    def test_references_consistency_endpoint(self, page):
        assert "/evidence/merkle-roots/" in page
        assert "consistency?previous_root_id=" in page

    def test_server_verified_messages_present(self, norm):
        for msg in ("Merkle consistency proof is server-verified.",
                    "Append-only consistency is not verified.",
                    "Historical leaf order was not stored, so consistency "
                    "proof cannot be reconstructed.",
                    "Merkle consistency proves append-only tree evolution "
                    "only; it does not prove legal validity."):
            assert msg in norm, msg

    def test_future_slots_labeled_not_implemented(self, norm):
        for msg in ("Checkpoint signatures are not implemented.",
                    "Witness cosignatures are not implemented.",
                    "SCITT receipts are not implemented."):
            assert msg in norm, msg

    def test_d3_not_always_not_exposed_when_data_exists(self, page):
        # The workbench now drives D3 from the server's append_only_verified,
        # not a permanent NOT_EXPOSED.
        assert "append_only_verified" in page
        assert "/consistency?previous_root_id=" in page
        # NOT_EXPOSED remains only the <2-checkpoint / no-permission fallback.
        assert "consistency == null ? 'NOT_EXPOSED'" in page

    def test_no_hardcoded_fake_consistency_proof_nodes(self, page):
        # Proof nodes come from the API response, never baked into the page.
        assert "c.data.consistency_proof_nodes" in page
        for fake in ("proof_node_0", "abc123deadbeef", "sha256:fake"):
            assert fake not in page, fake


def test_46_existing_portal_sections_still_served(page):
    # V-F did not remove any prior section (regression guard).
    for section in ('id="quotes-section"', 'id="evidence-section"',
                    'id="crm-section"', 'id="workbench-section"',
                    'id="admin-section"'):
        assert section in page, section
