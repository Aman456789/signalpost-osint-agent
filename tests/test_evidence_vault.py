import hashlib
import os

import pytest

from storage.evidence_vault import EvidenceVault, normalise_text

URLS = {"url": "https://example.no/", "final_url": "https://www.example.no/", "status": 200, "language": "no"}


def test_normalise_nfc_whitespace_and_hidden_characters():
    decomposed = "å"  # 'a' plus combining ring
    assert normalise_text(decomposed) == "å"
    assert normalise_text("a  \t b\r\n\r\n\r\n\r\nc") == "a b\n\nc"
    assert normalise_text("ab​c﻿") == "abc"


def test_normalise_twice_changes_nothing():
    once = normalise_text("  Vi  leverer\r\n\r\n\r\nfôr ​ ")
    assert normalise_text(once) == once


def test_save_writes_text_and_metadata(tmp_path):
    vault = EvidenceVault(tmp_path / "snapshots")
    snap = vault.save("Vi leverer fôr.", redirect_hops=["https://example.no/"], **URLS)
    assert snap.sha256 == hashlib.sha256("Vi leverer fôr.".encode("utf-8")).hexdigest()
    assert vault.load_text(snap.sha256) == "Vi leverer fôr."
    meta = vault.load_meta(snap.sha256)
    assert meta["url"] == "https://example.no/"
    assert meta["final_url"] == "https://www.example.no/"
    assert meta["status"] == 200
    assert meta["language"] == "no"
    assert meta["redirect_hops"] == ["https://example.no/"]
    assert meta["retrieved_at"].endswith("+00:00")


def test_same_text_is_stored_once(tmp_path):
    vault = EvidenceVault(tmp_path)
    first = vault.save("same  text", **URLS)
    second = vault.save("same text", **{**URLS, "url": "https://other.no/"})
    assert first.sha256 == second.sha256
    assert len(list(tmp_path.glob("*.txt"))) == 1
    assert vault.load_meta(first.sha256)["url"] == "https://example.no/"  # first retrieval is kept


def test_snapshot_is_read_only(tmp_path):
    vault = EvidenceVault(tmp_path)
    snap = vault.save("fixed", **URLS)
    mode = os.stat(tmp_path / f"{snap.sha256}.txt").st_mode & 0o777
    assert mode == 0o444


def test_changed_snapshot_is_detected(tmp_path):
    vault = EvidenceVault(tmp_path)
    snap = vault.save("original", **URLS)
    path = tmp_path / f"{snap.sha256}.txt"
    os.chmod(path, 0o644)
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError):
        vault.load_text(snap.sha256)
