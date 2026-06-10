"""Tests for tools/config.py: repo-relative paths and env-var overrides."""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

import tools.config

REPO_ROOT = Path(__file__).resolve().parent.parent

_ENV_VARS = ("DAYTRADING_TMP_DIR", "DAYTRADING_OUTPUT_DIR")


@pytest.fixture
def reload_config():
    """Restore the env vars and reload tools.config after the test so
    overridden paths can't leak into other tests. (Done manually rather
    than relying on monkeypatch teardown ordering: this fixture's
    finalizer runs before monkeypatch's undo.)"""
    saved = {k: os.environ.get(k) for k in _ENV_VARS}
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    importlib.reload(tools.config)


class TestDefaults:
    def test_repo_root(self) -> None:
        assert tools.config.REPO_ROOT == REPO_ROOT

    def test_paths_under_repo_root(self) -> None:
        cfg = tools.config
        for p in (cfg.TMP_DIR, cfg.OUTPUT_DIR, cfg.PRICE_CACHE_DIR, cfg.UNIVERSE_CSV):
            assert REPO_ROOT in p.parents, p

    def test_derived_paths(self) -> None:
        cfg = tools.config
        assert cfg.PRICE_CACHE_DIR == cfg.TMP_DIR / "prices"
        assert cfg.UNIVERSE_CSV == cfg.TMP_DIR / "universe.csv"

    def test_scanner_defaults(self) -> None:
        cfg = tools.config
        assert cfg.DEFAULT_MIN_PRICE == 5.0
        assert cfg.DEFAULT_MIN_VOLUME == 1_000_000
        assert cfg.DEFAULT_LOOKBACK_DAYS == 400
        assert cfg.UNIVERSE_REFRESH_DAYS == 7


class TestEnvOverrides:
    def test_tmp_dir_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reload_config
    ) -> None:
        override = tmp_path / "alt_tmp"
        monkeypatch.setenv("DAYTRADING_TMP_DIR", str(override))
        cfg = importlib.reload(tools.config)
        assert cfg.TMP_DIR == override
        assert cfg.PRICE_CACHE_DIR == override / "prices"
        assert cfg.UNIVERSE_CSV == override / "universe.csv"

    def test_output_dir_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reload_config
    ) -> None:
        override = tmp_path / "alt_out"
        monkeypatch.setenv("DAYTRADING_OUTPUT_DIR", str(override))
        cfg = importlib.reload(tools.config)
        assert cfg.OUTPUT_DIR == override
        # TMP_DIR untouched by the output override
        assert cfg.TMP_DIR == REPO_ROOT / ".tmp"
