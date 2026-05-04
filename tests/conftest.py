import os
import tempfile
import pytest


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.sqlite3")


@pytest.fixture
def tmp_audio_dir(tmp_path):
    d = tmp_path / "audio"
    d.mkdir()
    return str(d)
