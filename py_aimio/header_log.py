
"""
Formatting helpers for AIM processing logs.

By Matthias Walle.
"""

import re


_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _maybe_number(value):
    if _INT_RE.match(value):
        return int(value)
    if _FLOAT_RE.match(value):
        return float(value)
    return value


def log_to_dict(log):
    """Convert a formatted AIM log string into a dictionary.

    Example:
        >>> d = log_to_dict("Mu_Scaling                    8192")
        >>> d["Mu_Scaling"]
        8192
    """
    lines = log.split("\n")
    log_dict = {}

    for line in lines:
        if line.strip() and not line.startswith("!"):
            parts = re.split(r"\s{2,}", line.strip())
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) == 2:
                key, value = parts[0], parts[1]
                if value.startswith("[") and value.endswith("]"):
                    inner = value[1:-1].strip()
                    value = [_maybe_number(v) for v in inner.split()] if inner else []
                else:
                    value = _maybe_number(value)
            elif len(parts) > 2:
                key, value = parts[0], [_maybe_number(p) for p in parts[1:]]
            else:
                continue
            log_dict[key] = value

    return log_dict


def dict_to_log(log_dict):
    """Convert a dictionary into AIM processing-log text.

    Example:
        >>> s = dict_to_log({"Mu_Scaling": 8192})
        >>> "Mu_Scaling" in s
        True
    """
    log = "! Processing Log\n!\n!-------------------------------------------------------------------------------\n"
    split_line = "!-------------------------------------------------------------------------------\n"
    for key, value in log_dict.items():
        if isinstance(value, (int, float)):
            formatted_line = f"{key.ljust(30)}{value:>23}"
        elif isinstance(value, (list, tuple)):
            formatted_line = f"{key.ljust(30)}{' '.join([f'{v:>10}' for v in value])}"
        else:
            formatted_line = f"{key.ljust(30)}{value}".ljust(80)
        log += formatted_line + "\n"

        if key in ["Orig-ISQ-Dim-um", "Index Measurement", "Default-Eval", "HU: mu water", "Standard data deviation"]:
            log += split_line

    return log
