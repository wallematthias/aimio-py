from pathlib import Path

import numpy as np

from py_aimio import read_aim, write_aim


DATA_FILE = Path(__file__).parent.parent / "data" / "DB_07_DNN_DR_T1_TRAB_MASK.AIM"


def test_processing_log_edit_roundtrip(tmp_path):
    p = str(DATA_FILE)
    arr, meta = read_aim(p)

    # processing_log should be present and parsed to dict when possible
    proc = meta.get("processing_log")
    assert proc is not None
    if isinstance(proc, str):
        # if parsing failed earlier, skip this test
        return

    # mutate header
    proc["PYTEST_ROUNDTRIP_FIELD"] = 12345
    meta["processing_log"] = proc

    out = tmp_path / "edited.AIM"
    write_aim(str(out), arr, meta)

    arr2, meta2 = read_aim(str(out))
    assert arr2.shape == arr.shape
    # Ensure our edited field survived roundtrip
    proc2 = meta2.get("processing_log")
    assert isinstance(proc2, dict)
    assert proc2.get("PYTEST_ROUNDTRIP_FIELD") == 12345
