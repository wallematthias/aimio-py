from __future__ import annotations

import json

from py_aimio import cli


def test_cli_main_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "aim_info",
        lambda _p: {
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
    def _unexpected_aim_info(_p):
        raise AssertionError("AIM reader should not handle .ISQ files")

    monkeypatch.setattr(cli, "aim_info", _unexpected_aim_info)
    monkeypatch.setattr(
        cli,
        "isq_info",
        lambda _p: {"dimensions": (3, 2, 2), "mu_scaling": 4096},
        raising=False,
    )

    rc = cli.main(["scan.ISQ", "--indent", "0"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert rc == 0
    assert payload["dimensions"] == [3, 2, 2]
    assert payload["mu_scaling"] == 4096
