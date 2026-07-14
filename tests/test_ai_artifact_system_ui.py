"""CORE-A6 — Artifact System portal UI (static). Renders artifact list/detail,
status/trust/quarantine, hashes, claims, versions, verify/materialization
controls under no-execution labels. UI labels are convenience only."""
from finalis.portal.ui import PORTAL_PAGE


REQUIRED_LABELS = [
    "Artifact creation does not execute the action.",
    "Artifact creation does not send customer messages.",
    "Artifact creation does not call external providers.",
    "AI draft content is not human-verified truth.",
    "Claim graph records local support status; it does not create legal truth.",
    "Artifact quarantine preserves the artifact but blocks readiness and "
    "future use.",
    "Server-side artifact truth is authoritative.",
    "Document export is not implemented in this mission.",
    "C2PA/Sigstore/DSSE/SLSA/in-toto are not implemented in this mission.",
]


class TestArtifactUi:
    def test_section_present(self):
        assert 'id="artifacts-section"' in PORTAL_PAGE
        assert "Artifact System" in PORTAL_PAGE

    def test_loader_registered(self):
        assert "loadArtifactsSection" in PORTAL_PAGE
        assert "if (window.loadArtifactsSection)" in PORTAL_PAGE

    def test_all_required_labels_present(self):
        for lbl in REQUIRED_LABELS:
            assert lbl in PORTAL_PAGE, f"missing label: {lbl}"

    def test_controls_present(self):
        for fn in ["openArtifact", "verifyArtifact", "materializeArtifact"]:
            assert fn in PORTAL_PAGE

    def test_reads_from_server_endpoints(self):
        assert "get('/ai-artifacts')" in PORTAL_PAGE
        assert "'/ai-artifacts/' + id + '/claims'" in PORTAL_PAGE
        assert "/materialization-check" in PORTAL_PAGE

    def test_shows_claims_and_versions(self):
        assert "Claims (" in PORTAL_PAGE
        assert "Versions (" in PORTAL_PAGE
