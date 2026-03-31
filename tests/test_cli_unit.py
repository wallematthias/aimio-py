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

