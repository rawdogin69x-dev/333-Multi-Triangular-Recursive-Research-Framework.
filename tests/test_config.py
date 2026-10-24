import pytest

from akashic.config import load


def test_defaults_when_missing(tmp_path):
    cfg = load(tmp_path / "nope.yaml")
    assert cfg.gravity.k_base == 2 and cfg.weights.of("EXECUTED") == 0.95


def test_example_config_loads():
    cfg = load("config/akashic.example.yaml")
    assert cfg.embed_dims == 1024 and cfg.gravity.topic_depth == 2


def test_unknown_keys_are_refused(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("dbpath: x\n")
    with pytest.raises(ValueError):
        load(p)
