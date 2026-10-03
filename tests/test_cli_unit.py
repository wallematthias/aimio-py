from __future__ import annotations

import json
import struct

from py_aimio import cli


def test_cli_main_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "image_info",
        lambda _p, format="auto": {
            "dimensions": (4, 5, 6),
            "position": (10, 20, 0),
            "spacing": (0.082, 0.082, 0.082),
        },
    )

    rc = cli.main(["scan.AIM", "--indent", "0"])
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)

    assert rc == 0
    assert payload["dimensions"] == [4, 5, 6]
    assert payload["position"] == [10, 20, 0]


def test_cli_main_dispatches_isq_files_to_isq_info(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "image_info",
        lambda _p, format="auto": {"dimensions": (3, 2, 2), "format_arg": format, "mu_scaling": 4096},
    )

    rc = cli.main(["scan.ISQ", "--indent", "0"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert rc == 0
    assert payload["dimensions"] == [3, 2, 2]
    assert payload["format_arg"] == "auto"
    assert payload["mu_scaling"] == 4096


def test_cli_main_passes_format_to_image_info(monkeypatch, capsys):
    calls = []

    def _image_info(path, format="auto"):
        calls.append((path, format))
        return {"dimensions": (6, 5, 1), "format": "GOBJ"}

    monkeypatch.setattr(cli, "image_info", _image_info)

    rc = cli.main(["mask.GOBJ;1", "--format", "gobj", "--indent", "0"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert rc == 0
    assert calls == [("mask.GOBJ;1", "gobj")]
    assert payload["dimensions"] == [6, 5, 1]
    assert payload["format"] == "GOBJ"


def test_cli_reads_rsq_metadata_as_json(tmp_path, capsys):
    path = tmp_path / "synthetic.RSQ;1"
    header = bytearray(512)
    header[:16] = b"CTDATA-HEADER_V1"
    struct.pack_into("<3I", header, 44, 1, 1, 1)
    path.write_bytes(header + b"\xff\xff")

    rc = cli.main([str(path), "--format", "rsq", "--indent", "0"])
    info = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert info["shape"] == [1, 1, 1]
    assert info["dtype"] == "<u2"
    assert info["header_words"][11:14] == [1, 1, 1]
    assert info["beam_hardening"]["available"] is False
