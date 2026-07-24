"""Atomic registry save + mid-write load retry."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import yaml

from trader_platform.hypothesis_registry import HypothesisRegistry


def test_save_is_atomic_and_loadable(tmp_path: Path) -> None:
    path = tmp_path / "hypotheses.yaml"
    reg = HypothesisRegistry(path)
    store = {
        "version": 1,
        "hypotheses": [
            {
                "id": "h1",
                "name": "n",
                "thesis": "t",
                "sleeve": "premium",
                "instruments": ["BAC"],
                "status": "testing",
                "created": "2026-07-24T00:00:00+00:00",
                "updated": "2026-07-24T00:00:00+00:00",
            }
        ],
    }
    reg.save(store)
    assert path.exists()
    assert not list(tmp_path.glob(".hypotheses.yaml.*.tmp"))
    loaded = reg.load()
    assert loaded["hypotheses"][0]["id"] == "h1"


def test_load_retries_through_transient_corrupt_yaml(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "hypotheses.yaml"
    good = {"version": 1, "hypotheses": []}
    path.write_text("version: 1\nhypotheses: []\n")
    reg = HypothesisRegistry(path)

    calls = {"n": 0}
    real_safe_load = yaml.safe_load

    def flaky_safe_load(stream):
        calls["n"] += 1
        if calls["n"] < 3:
            raise yaml.scanner.ScannerError(
                "while scanning",
                None,
                "found unexpected end of stream",
                None,
            )
        return real_safe_load(stream)

    monkeypatch.setattr(yaml, "safe_load", flaky_safe_load)
    out = reg.load(retries=5, retry_sleep_s=0.001)
    assert out["version"] == 1
    assert calls["n"] == 3
    assert good["hypotheses"] == out["hypotheses"]


def test_concurrent_reader_never_sees_truncated_live_path(tmp_path: Path) -> None:
    """While save dumps to temp, live path stays prior complete YAML."""
    path = tmp_path / "hypotheses.yaml"
    reg = HypothesisRegistry(path)
    reg.save({"version": 1, "hypotheses": [{"id": "old", "name": "o", "thesis": "t", "sleeve": "premium", "status": "candidate", "created": "x", "updated": "x"}]})

    # Slow dump: monkeypatch safe_dump to sleep after writing a bit is hard;
    # instead prove replace semantics: write temp then replace, intermediate live is old.
    errors: list[Exception] = []
    reads: list[str] = []

    def reader() -> None:
        r = HypothesisRegistry(path)
        for _ in range(40):
            try:
                data = r.load(retries=1, retry_sleep_s=0.0)
                hid = (data.get("hypotheses") or [{}])[0].get("id")
                reads.append(str(hid))
            except Exception as e:  # noqa: BLE001 — collect race failures
                errors.append(e)
            time.sleep(0.005)

    t = threading.Thread(target=reader)
    t.start()
    for i in range(5):
        reg.save(
            {
                "version": 1,
                "hypotheses": [
                    {
                        "id": f"new{i}",
                        "name": "n",
                        "thesis": "t",
                        "sleeve": "premium",
                        "status": "candidate",
                        "created": "x",
                        "updated": "x",
                    }
                ],
            }
        )
        time.sleep(0.01)
    t.join(timeout=5)
    assert not errors, errors
    assert reads
    assert all(x in {"old", "new0", "new1", "new2", "new3", "new4"} for x in reads)
