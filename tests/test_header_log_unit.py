from py_aimio.header_log import dict_to_log, log_to_dict


def test_log_to_dict_parses_bracket_lists_and_strings():
    log = (
        "Vector                         [1 2 3.5]\n"
        "Name                           sample_text\n"
        "BadSingleToken\n"
    )
    parsed = log_to_dict(log)
    assert parsed["Vector"] == [1, 2, 3.5]
    assert parsed["Name"] == "sample_text"


def test_log_to_dict_parses_multi_value_rows():
    log = "Triple                         1  2  3\n"
    parsed = log_to_dict(log)
    assert parsed["Triple"] == [1, 2, 3]


def test_dict_to_log_formats_list_and_text_values():
    out = dict_to_log({"ListVal": [1, 2, 3], "Comment": "hello world"})
    assert "ListVal" in out
    assert "Comment" in out
    assert "hello world" in out
