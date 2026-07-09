"""TOOL-B3 contract versioning + diff.

Creating a contract records version 1 with a contract-version hash chain; the
/versions endpoint lists it with contract + abi hashes; /diff reports
non-comparable until a second version exists.
"""
from conftest import OWNER, VIEWER
from finalis.ai_employee import tool_contracts as tc


class TestVersionsEndpoint:
    def test_create_records_one_version(self, gate):
        tid, c = gate.contracted_tool()
        vs = gate.ct(tid, c["contract_id"], path="/versions").json()
        assert vs["count"] == 1

    def test_first_version_number_is_one(self, gate):
        tid, c = gate.contracted_tool()
        vs = gate.ct(tid, c["contract_id"], path="/versions").json()
        assert vs["versions"][0]["version_number"] == 1

    def test_version_lists_contract_hash(self, gate):
        tid, c = gate.contracted_tool()
        vs = gate.ct(tid, c["contract_id"], path="/versions").json()
        assert vs["versions"][0]["contract_hash"] == c["contract_hash"]

    def test_version_lists_abi_hash(self, gate):
        tid, c = gate.contracted_tool()
        vs = gate.ct(tid, c["contract_id"], path="/versions").json()
        assert vs["versions"][0]["contract_abi"]["abi_hash"] == \
            c["contract_abi"]["abi_hash"]

    def test_versions_carries_honesty_labels(self, gate):
        tid, c = gate.contracted_tool()
        vs = gate.ct(tid, c["contract_id"], path="/versions").json()
        assert isinstance(vs["honesty_labels"], list) and vs["honesty_labels"]

    def test_versions_unknown_contract_404(self, gate):
        tid = gate.contract_tool()
        assert gate.ct(tid, "nope", path="/versions").status_code == 404

    def test_versions_readable_by_viewer(self, gate):
        # /versions is a case.read surface.
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], path="/versions", actor=VIEWER)
        assert r.status_code == 200


class TestStoredVersionChain:
    def _row(self, gate, contract_id):
        return gate.db.one(
            "SELECT version_number, contract_hash, contract_abi_hash, "
            "contract_version_hash, contract_chain_hash, "
            "previous_contract_version_hash FROM ai_tool_contract_versions "
            "WHERE contract_id=? ORDER BY version_number", contract_id)

    def test_stored_version_has_contract_version_hash(self, gate):
        tid, c = gate.contracted_tool()
        row = self._row(gate, c["contract_id"])
        assert row["contract_version_hash"]

    def test_stored_version_has_contract_chain_hash(self, gate):
        tid, c = gate.contracted_tool()
        row = self._row(gate, c["contract_id"])
        assert row["contract_chain_hash"]

    def test_first_version_has_no_predecessor(self, gate):
        tid, c = gate.contracted_tool()
        row = self._row(gate, c["contract_id"])
        assert row["previous_contract_version_hash"] is None

    def test_version_hash_matches_recomputation(self, gate):
        tid, c = gate.contracted_tool()
        row = self._row(gate, c["contract_id"])
        expected = tc.contract_version_hash(
            contract_id=c["contract_id"], version_number=1,
            contract_hash=c["contract_hash"],
            abi_hash=c["contract_abi"]["abi_hash"],
            previous_contract_version_hash=None)
        assert row["contract_version_hash"] == expected

    def test_chain_hash_matches_recomputation(self, gate):
        tid, c = gate.contracted_tool()
        row = self._row(gate, c["contract_id"])
        assert row["contract_chain_hash"] == tc.contract_chain_hash(
            None, row["contract_version_hash"])

    def test_stored_version_hashes_agree_with_contract(self, gate):
        tid, c = gate.contracted_tool()
        row = self._row(gate, c["contract_id"])
        assert row["contract_hash"] == c["contract_hash"]
        assert row["contract_abi_hash"] == c["contract_abi"]["abi_hash"]


class TestDiff:
    def test_single_version_not_comparable(self, gate):
        tid, c = gate.contracted_tool()
        d = gate.ct(tid, c["contract_id"], path="/diff", method="POST").json()
        assert d["comparable"] is False

    def test_single_version_diff_has_note(self, gate):
        tid, c = gate.contracted_tool()
        d = gate.ct(tid, c["contract_id"], path="/diff", method="POST").json()
        assert "note" in d
        assert isinstance(d["honesty_labels"], list) and d["honesty_labels"]

    def test_diff_unknown_contract_404(self, gate):
        tid = gate.contract_tool()
        assert gate.ct(tid, "nope", path="/diff",
                       method="POST").status_code == 404
