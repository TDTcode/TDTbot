import json
import os

import pytest

from TDTbot import param


class DummyDataContainer(param.DataContainer):
    def _gen_data(self, key):
        # populate with a deterministic default if missing
        if key is None:
            self.data["generated"] = "value"
        elif key == "computed":
            self.data[key] = "computed-value"
        else:
            raise NotImplementedError


def test_parameters_string2ids_and_dget(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"custom": "42", "ignore_list": "debugging"}))
    p = param.Parameters(copy={"nemeses": "electro,wator"}, config=str(cfg), token=None, roasts=None)

    # string2ids converts numeric strings to ints and aliases to IDs
    p.string2ids("custom", "ignore_list", "nemeses")
    assert p["custom"] == 42
    assert p["ignore_list"] == param.channels.debugging
    assert p["nemeses"] == [param.users.electro, param.users.wator]

    # dget falls back to defaults
    assert p.dget("cmd_prefix") == param.defaults["cmd_prefix"]


def test_read_token_and_roasts(tmp_path):
    token_file = tmp_path / "token.txt"
    token_file.write_text("abc123\n")
    roast_file = tmp_path / "roasts.txt"
    roast_file.write_text("line1\nline2\n")

    p = param.Parameters(copy={}, config=None, token=str(token_file), roasts=str(roast_file))
    assert p["token"] == "abc123"
    assert p["roasts"] == ["line1", "line2"]


def test_read_config_merges_into_parameters(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"cmd_prefix": ["!"], "timezone": "UTC"}))

    p = param.Parameters(copy={}, config=str(cfg), token=None, roasts=None)
    assert p["cmd_prefix"] == ["!"]
    assert p["timezone"] == "UTC"


def test_datacontainer_generation_and_set_if_not_set(tmp_path):
    fn = tmp_path / "data.json"
    dc = DummyDataContainer(str(fn))

    # _gen_data(None) seeds generated; __getitem__ triggers compute
    assert dc["generated"] == "value"

    # computed is generated on demand and persisted
    assert dc["computed"] == "computed-value"
    dc["new"] = "fresh"
    assert dc["new"] == "fresh"

    # set_if_not_set respects existing value
    dc.set_if_not_set("new", "other")
    assert dc["new"] == "fresh"
    dc.set_if_not_set("another", "val")
    assert dc["another"] == "val"

    # reload from disk retains values
    dc2 = DummyDataContainer(str(fn))
    assert dc2["computed"] == "computed-value"
    assert dc2["another"] == "val"


def test_permadict_basic_ops(tmp_path):
    path = tmp_path / "shelf"
    store = param.PermaDict(str(path))

    store["a"] = 1
    store["b"] = 2
    assert "a" in store and "b" in store
    assert store["a"] == 1
    assert store.get("missing", 0) == 0

    store.delete("a")
    assert "a" not in store
    assert set(store.keys()) == {"b"}

    popped = store.pop("b")
    assert popped == 2
    assert "b" not in store


def test_intpermadict_coerces_keys(tmp_path):
    path = tmp_path / "intshelf"
    store = param.IntPermaDict(str(path))

    store["1"] = "one"
    store[2] = "two"
    assert 1 in store and 2 in store
    assert store[1] == "one"
    assert store[2] == "two"
    assert set(store.keys()) == {1, 2}
