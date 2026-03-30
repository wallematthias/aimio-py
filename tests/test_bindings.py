import os
from pathlib import Path

import numpy as np

from py_aimio import aim_info, read_aim, write_aim


DATA_FILE = Path(__file__).parent.parent / "data" / "DB_07_DNN_DR_T1_TRAB_MASK.AIM"


def test_aim_info_and_read():
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
