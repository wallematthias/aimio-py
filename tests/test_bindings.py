from pathlib import Path

import numpy as np
import pytest

from py_aimio import aim_info, read_aim, write_aim


DATA_FILE = Path(__file__).parent.parent / "data" / "DB_07_DNN_DR_T1_TRAB_MASK.AIM"


def _require_sample_data() -> None:
    if not DATA_FILE.exists():
        pytest.skip(f"Sample AIM test data not available: {DATA_FILE}")


def test_aim_info_and_read():
    _require_sample_data()
    p = str(DATA_FILE)
    info = aim_info(p)
    assert "dimensions" in info
    arr, meta = read_aim(p)
    assert isinstance(arr, np.ndarray)
    assert arr.size > 0
    # ensure metadata dimensions match the array when available
    if "dimensions" in meta:
        md = tuple(meta["dimensions"])
        ashp = tuple(arr.shape)
        # metadata may be (x,y,z) while numpy array is (z,y,x)
        assert md == ashp or md[::-1] == ashp


def test_roundtrip(tmp_path):
    _require_sample_data()
    p = str(DATA_FILE)
    arr, meta = read_aim(p)
    out = tmp_path / "out.AIM"
    write_aim(str(out), arr, meta)
    arr2, meta2 = read_aim(str(out))
    assert arr.shape == arr2.shape
    assert np.array_equal(arr, arr2)
    for key in ("dimensions", "buffer_type", "element_size"):
        if key in meta:
            assert meta2.get(key) == meta.get(key)


def test_write_preserves_position_and_offset_metadata(tmp_path):
    arr = np.zeros((4, 5, 6), dtype=np.int16)
    meta = {
        "element_size": (0.061, 0.062, 0.063),
        "position": (930, 702, 11),
        "offset": (1, 2, 3),
    }

    out = tmp_path / "positioned.AIM"
    write_aim(str(out), arr, meta)
    _arr2, meta2 = read_aim(str(out))

    assert meta2["dimensions"] == (6, 5, 4)
    assert meta2["position"] == meta["position"]
    assert meta2["offset"] == meta["offset"]
