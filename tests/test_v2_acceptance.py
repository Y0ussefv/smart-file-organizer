"""
Acceptance tests T01–T28 of the V2 specification (§11), on synthetic documents.
T09 / T10 (sub-folder proposals) belong to the P2 phase and are not covered yet.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.bee import ledger as L
from src.bee.matcher import PROPOSE, Candidate, decide
from src.bee.ledger import Project
from src.bee.mover import MoveRefused
from src.watcher.download_watcher import DownloadWatcher, is_candidate
from tests.v2_helpers import (BEESTART_REPORT, GIZ_HYDROGEN, SINELAC_AUDIT, SINELAC_CONTRACT, YM, env,  # noqa: F401
                              net)


def test_T01_strong_match_is_renamed_and_filed_with_undo(env, net):
    env.pipe.create_project("SINELAC", refs=["SIN-2026-04"])
    r = env.pipe.process_new_item(env.doc("download (3).txt", SINELAC_CONTRACT))
    assert r["status"] == "FILED"
    assert r["new_name"].startswith(f"{YM} ") and "Sinelac" in r["new_name"]
    assert Path(r["new_path"]).parent == env.projets / "SINELAC"
    assert r["batch_id"] and env.ledger.operations(r["batch_id"])


@pytest.mark.parametrize("alias", [None, "GIZ"])
def test_T02_giz_report_never_filed_into_beestart(env, net, alias):
    env.pipe.create_project("BeeStart", aliases=[alias] if alias else [])
    r = env.pipe.process_new_item(env.doc("rapport.txt", GIZ_HYDROGEN))
    assert r["status"] != "FILED"
    assert not (env.projets / "BeeStart").exists()
    assert Path(r["new_path"]).parent == env.dl
    if alias:
        assert r.get("proposed_project") == "BeeStart"  # a proposal at most, never a move


def _three_delfa(env):
    out = []
    for i, text in enumerate(["Projet Delfa : cahier des charges du site web",
                              "Projet Delfa : devis graphique et charte",
                              "Projet Delfa : compte rendu de la reunion de lancement"]):
        out.append(env.pipe.process_new_item(env.doc(f"doc{i}.txt", text + " " + "x " * 30)))
    return out


def test_T03_three_files_of_a_new_project_give_one_proposal_and_no_folder(env, net):
    results = _three_delfa(env)
    props = env.ledger.proposals(kind="new_project")
    assert len(props) == 1 and props[0]["payload"]["name"] == "Delfa"
    assert len(props[0]["payload"]["files"]) == 3
    assert results[-1].get("new_project_proposal")
    assert not env.projets.exists()
    out = env.pipe.accept_proposal(props[0]["proposal_id"])
    assert len(out["moved"]) == 3
    assert sorted(p.parent.name for p in (env.projets / "Delfa").iterdir()) == ["Delfa"] * 3


def test_T04_refused_new_project_creates_nothing(env, net):
    _three_delfa(env)
    prop = env.ledger.proposals(kind="new_project")[0]
    env.pipe.refuse_proposal(prop["proposal_id"])
    assert not env.projets.exists()
    assert len(env.root_files()) == 3
    env.pipe.process_new_item(env.doc("doc4.txt", "Projet Delfa : annexe technique " + "y " * 30))
    assert len(env.ledger.proposals(kind="new_project")) == 0  # not proposed again


def test_T05_two_files_only_no_folder_but_manual_creation(env, net):
    for i in range(2):
        env.pipe.process_new_item(env.doc(f"d{i}.txt", f"Projet Orion : note {i} " + "z " * 30))
    assert env.ledger.proposals(kind="new_project") == []
    assert not env.projets.exists()
    p = env.pipe.create_project("Orion")
    assert env.ledger.project(p.project_id).name == "Orion"


def test_T06_two_unrelated_contracts_are_not_linked(env, net):
    env.pipe.create_project("SINELAC", refs=["SIN-2026-04"])
    a = env.pipe.process_new_item(env.doc("c1.txt", "Contrat de location entre Dupont SPRL et Martin, bail commercial."))
    b = env.pipe.process_new_item(env.doc("c2.txt", "Contrat de maintenance entre Lemaire SA et Garage Central."))
    assert a["decision"] == "KEEP" and b["decision"] == "KEEP"
    assert env.ledger.proposals() == []


def test_T07_unreadable_file_kept_with_its_name(env, net):
    f = env.dl / "blob.bin"
    f.write_bytes(bytes(range(256)) * 4)
    r = env.pipe.process_new_item(f)
    assert r["new_name"] == "blob.bin" and Path(r["new_path"]).parent == env.dl
    assert r["sensitivity"] == "INCONNU"


def test_T08_no_recent_folder_memory(env, net):
    env.pipe.create_project("SINELAC", refs=["SIN-2026-04"])
    env.pipe.create_project("BeeStart", refs=["BST-2026"])
    b = env.pipe.process_new_item(env.doc("b.txt", BEESTART_REPORT + " Reference BST-2026."))
    assert b["status"] == "FILED" and "BeeStart" in b["new_path"]
    a = env.pipe.process_new_item(env.doc("a.txt", SINELAC_AUDIT))
    assert a["status"] == "FILED" and Path(a["new_path"]).parent.name == "SINELAC"
    n = env.pipe.process_new_item(env.doc("n.txt", "Note neutre sur l'organisation des bureaux. " * 3))
    assert Path(n["new_path"]).parent == env.dl


def test_T11_category_path_is_at_most_project_category(env, net):
    p = env.pipe.create_project("SINELAC", refs=["SIN-2026-04"])
    env.pipe.add_category(p.project_id, "Contrats", ["Contrat"])
    r = env.pipe.process_new_item(env.doc("x.txt", SINELAC_CONTRACT))
    rel = Path(r["new_path"]).relative_to(env.projets)
    assert rel.parts[:2] == ("SINELAC", "Contrats") and len(rel.parts) == 3


def test_T12_deeper_target_is_refused_without_creating_anything(env, net):
    env.pipe.create_project("SINELAC")
    f = env.doc("f.txt", "x")
    batch = env.ledger.new_batch("t")
    with pytest.raises(MoveRefused):
        env.pipe.mover.move(batch, None, f, env.projets / "SINELAC" / "Contrats" / "2026")
    assert not env.projets.exists() and f.exists()


def test_T13_downloads_in_progress_are_not_touched(tmp_path):
    seen = []
    w = DownloadWatcher(tmp_path, lambda p: seen.append(p.name) or {}, settle_seconds=6)
    w.snapshot_existing()
    assert not is_candidate(Path("rapport.pdf.crdownload"))
    f = tmp_path / "rapport.pdf"
    for t, size in ((100, 10), (103, 20), (106, 30)):
        f.write_bytes(b"x" * size)
        w.poll_once(now=t)
    assert seen == []  # still growing


def test_T14_files_present_at_start_are_left_alone(tmp_path):
    (tmp_path / "old.pdf").write_bytes(b"%PDF-1.4 old")
    seen = []
    w = DownloadWatcher(tmp_path, lambda p: seen.append(p.name) or {}, settle_seconds=0)
    w.snapshot_existing()
    w.poll_once(now=10)
    w.poll_once(now=20)
    assert seen == []


def test_T15_already_prefixed_no_second_prefix_no_loop(env, net):
    f = env.doc(f"{YM} Rapport_Deja_Nomme.txt", SINELAC_AUDIT)
    r1 = env.pipe.process_new_item(f)
    assert r1["new_name"] == f.name
    r2 = env.pipe.process_new_item(Path(r1["new_path"]))
    assert r2["status"] == "SKIPPED"
    assert not is_candidate(f)


def test_T16_collision_uses_suffix_and_keeps_both(env, net):
    first = env.pipe.process_new_item(env.doc("a.txt", BEESTART_REPORT))
    second = env.pipe.process_new_item(env.doc("b.txt", BEESTART_REPORT + " Deuxieme version."))
    assert first["new_name"] != second["new_name"]
    assert Path(second["new_name"]).stem.endswith("_2")
    assert Path(first["new_path"]).read_text(encoding="utf-8") == BEESTART_REPORT


def test_T17_restart_during_processing(env, net):
    env.pipe.create_project("SINELAC", refs=["SIN-2026-04"])
    f = env.doc("download.txt", SINELAC_AUDIT)
    # crash between "planned" and the actual move: the operation stays planned, the file untouched
    fid = env.ledger.new_file("hash", f)
    batch = env.ledger.new_batch("crash")
    env.ledger.plan_op(batch, fid, "move", f, env.projets / "SINELAC" / "x.txt")
    env.ledger.update_file(fid, state=L.ANALYSING)
    out = env.pipe.recover()
    assert out["recovered"] >= 2
    assert env.ledger.file(fid)["state"] == L.FAILED and f.exists()
    r = env.pipe.process_new_item(f)            # controlled resume: processed once
    again = env.pipe.process_new_item(Path(r["new_path"]))
    assert again["status"] == "SKIPPED"
    assert env.all_files() == [f"Projets/SINELAC/{Path(r['new_path']).name}"]


def test_T18_api_failure_falls_back_locally_without_arbitrary_move(env, net):
    import requests
    env.pipe.set_cloud(True)
    env.pipe.create_project("BeeStart", refs=["BST-2026"])
    env.pipe.process_new_item(env.doc("b.txt", BEESTART_REPORT + " BST-2026"))
    net.fail = requests.exceptions.ConnectionError("down")
    r = env.pipe.process_new_item(env.doc("x.txt", "Brochure publique sur la mobilite douce en ville " * 3))
    assert Path(r["new_path"]).parent == env.dl
    assert r["cloud"] == "local"


def test_T19_local_only_contract_sends_nothing(env, net):
    r = env.pipe.process_new_item(env.doc("c.txt", SINELAC_CONTRACT + " Confidentiel."))
    assert net.calls == [] and r["sensitivity"] in ("P1", "P2")


def test_T20_undo_after_rename_and_move(env, net):
    env.pipe.create_project("SINELAC", refs=["SIN-2026-04"])
    f = env.doc("download (3).txt", SINELAC_AUDIT)
    r = env.pipe.process_new_item(f)
    assert r["status"] == "FILED"
    u = env.pipe.undo(r["batch_id"])
    assert u["status"] == "REVERTED"
    assert f.exists() and f.read_text(encoding="utf-8") == SINELAC_AUDIT
    assert not env.projets.exists()


def test_T21_one_off_correction_is_not_a_general_rule(env, net):
    env.pipe.create_project("BeeStart", aliases=["GIZ"])
    hydro = env.pipe.create_project("Hydrogene")
    r = env.pipe.process_new_item(env.doc("g1.txt", GIZ_HYDROGEN))
    env.pipe.move_file_to_project(r["file_id"], hydro.project_id)
    r2 = env.pipe.process_new_item(env.doc("g2.txt", GIZ_HYDROGEN + " Annexe 2 sur le transport."))
    assert r2["status"] != "FILED"
    assert Path(r2["new_path"]).parent == env.dl


def test_T22_software_project_is_left_unchanged(env, net):
    repo = env.dl / "my-app"
    (repo / ".git").mkdir(parents=True)
    (repo / "package.json").write_text("{}", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "index.js").write_text("console.log(1)", encoding="utf-8")
    before = sorted(str(p.relative_to(repo)) for p in repo.rglob("*"))
    r = env.pipe.process_new_item(repo)
    assert r["status"] == "SKIPPED"
    assert sorted(str(p.relative_to(repo)) for p in repo.rglob("*")) == before


def test_T23_archive_and_unzipped_folder_not_restructured(env, net):
    import zipfile
    z = env.dl / "pack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a/b/c/file.txt", "hello")
    r = env.pipe.process_new_item(z)
    assert Path(r["new_path"]).parent == env.dl and r["sensitivity"] == "INCONNU"
    nested = env.dl / "unzipped" / "inner" / "deeper"
    nested.mkdir(parents=True)
    (nested / "f.txt").write_text("x", encoding="utf-8")
    assert env.pipe.process_new_item(env.dl / "unzipped")["status"] == "SKIPPED"
    assert (nested / "f.txt").exists()


def test_T24_failed_move_leaves_no_orphan_folder(env, net):
    env.pipe.create_project("SINELAC", refs=["SIN-2026-04"])
    env.pipe.mover.fail_after_mkdir = True
    f = env.doc("x.txt", SINELAC_AUDIT)
    r = env.pipe.process_new_item(f)
    assert r["status"] == "ERROR"
    assert not env.projets.exists()
    assert len(env.root_files()) == 1


def test_T25_close_scores_give_a_proposal_only():
    a = Candidate(Project("a", "A", "/p/A"), 96, ["name"])
    b = Candidate(Project("b", "B", "/p/B"), 93, ["name"])
    d = decide([a, b])
    assert d.choice == PROPOSE and "close" in d.reason


def test_T26_duplicates_are_flagged_never_deleted(env, net):
    a = env.pipe.process_new_item(env.doc("one.txt", BEESTART_REPORT))
    b = env.pipe.process_new_item(env.doc("two.txt", BEESTART_REPORT))
    assert Path(a["new_path"]).exists() and Path(b["new_path"]).exists()
    assert b.get("duplicate_of")


def test_T27_pending_proposal_does_not_block_the_next_download(env, net):
    env.pipe.create_project("BeeStart", aliases=["GIZ"])
    first = env.pipe.process_new_item(env.doc("g.txt", GIZ_HYDROGEN))
    pending = env.ledger.proposals()
    assert len(pending) == 1
    second = env.pipe.process_new_item(env.doc("n.txt", "Note interne sur le recrutement des stagiaires. " * 2))
    assert second["status"] in ("RENAMED", "UNCHANGED")
    assert env.ledger.proposals() == pending and Path(first["new_path"]).exists()


def test_T28_symlink_leaving_the_area_is_refused(env, net, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = env.dl / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not allowed on this machine")
    with patch("src.bee.pipeline.read_local") as reader:
        r = env.pipe.process_new_item(link)
    assert r["status"] == "ERROR" and not reader.called
    assert outside.read_text(encoding="utf-8") == "secret"
