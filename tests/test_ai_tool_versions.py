"""TOOL-B1 — append-only descriptor version chain and lineage.

New versions increment monotonically and hash-link to their predecessor;
terminal-status tools reject new versions; lineage reports every version.
"""
from conftest import OWNER, MANAGER


def _add_version(gate, tool_id, actor=OWNER, **over):
    return gate.tool(tool_id, "/versions", actor=actor, method="POST",
                     **gate.clean_tool_body(**over))


class TestAddVersion:
    def test_add_version_increments_number(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = _add_version(gate, tid, tool_description="v2").json()
        assert r["version_number"] == 2
        assert r["tool_id"] == tid
        assert isinstance(r["honesty_labels"], list) and r["honesty_labels"]

    def test_third_version_number(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        _add_version(gate, tid, tool_description="v2")
        r = _add_version(gate, tid, tool_description="v3").json()
        assert r["version_number"] == 3

    def test_version_links_to_previous(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        v1 = gate.latest_tool_version(tid)
        r = _add_version(gate, tid, tool_description="v2").json()
        assert r["tool_version"]["previous_version_hash"] == v1["version_hash"]

    def test_chain_hash_links_across_three_versions(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        _add_version(gate, tid, tool_description="v2")
        v2 = gate.latest_tool_version(tid)
        r3 = _add_version(gate, tid, tool_description="v3").json()
        assert r3["tool_version"]["previous_version_hash"] == v2["version_hash"]

    def test_manager_can_add_version(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        assert _add_version(gate, tid, actor=MANAGER,
                            tool_description="v2").status_code == 200

    def test_add_version_returns_supply_chain(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = _add_version(gate, tid, tool_description="v2").json()
        assert "supply_chain" in r
        assert r["supply_chain"]["verdict"] in ("STABLE", "DRIFT_DETECTED",
                                                "RUG_PULL_DETECTED")


class TestGetVersions:
    def test_list_versions(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        _add_version(gate, tid, tool_description="v2")
        vs = gate.c.get(f"/ai-tools/{tid}/versions",
                        headers=gate.h(OWNER)).json()["versions"]
        assert [v["version_number"] for v in vs] == [1, 2]

    def test_get_single_version(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        _add_version(gate, tid, tool_description="v2")
        v = gate.tool(tid, f"/versions/{tid}-v2", actor=OWNER).json()
        assert v["version_number"] == 2
        assert v["tool_version_id"] == f"{tid}-v2"

    def test_get_unknown_version_404(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        assert gate.tool(tid, f"/versions/{tid}-v9",
                         actor=OWNER).status_code == 404


class TestTerminalBlocksVersions:
    def test_superseded_tool_blocks_new_version(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        sup = gate.tool(tid, "/supersede", actor=OWNER, method="POST")
        assert sup.status_code == 200
        assert sup.json()["status"] == "SUPERSEDED"
        blocked = _add_version(gate, tid, tool_description="v2")
        assert blocked.status_code == 409

    def test_supersede_is_terminal_admit_blocked(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        gate.tool(tid, "/supersede", actor=OWNER, method="POST")
        assert gate.admit_tool(tid, actor=OWNER).status_code == 409

    def test_disabled_tool_blocks_new_version(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        d = gate.tool(tid, "/disable", actor=OWNER, method="POST")
        assert d.status_code == 200
        # A governor's DISABLED stop must not be erasable by re-versioning
        # through case.update; the tool must be re-enabled via governance first.
        assert _add_version(gate, tid, tool_description="v2").status_code == 409


class TestLineage:
    def test_lineage_lists_all_versions(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        _add_version(gate, tid, tool_description="v2")
        _add_version(gate, tid, tool_description="v3")
        lin = gate.tool(tid, "/lineage", actor=OWNER).json()
        assert [e["version_number"] for e in lin["lineage"]] == [1, 2, 3]
        assert lin["tool_key"] == "search-cases"

    def test_lineage_chain_fields(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        _add_version(gate, tid, tool_description="v2")
        lin = gate.tool(tid, "/lineage", actor=OWNER).json()
        first, second = lin["lineage"]
        assert first["previous_version_hash"] is None
        assert second["previous_version_hash"] == first["version_hash"]
