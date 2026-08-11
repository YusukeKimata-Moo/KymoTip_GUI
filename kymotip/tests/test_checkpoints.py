import pytest

from kymotip.segmentation.checkpoints import (
    BUNDLED_CHECKPOINTS,
    CheckpointDownloadError,
    checkpoint_path,
    ensure_checkpoint,
    is_checkpoint_available,
)


def test_checkpoint_path_unknown_name_raises(tmp_path):
    with pytest.raises(ValueError):
        checkpoint_path(tmp_path, "unknown")


def test_is_checkpoint_available_false_when_missing(tmp_path):
    assert is_checkpoint_available(tmp_path, "small") is False


def test_ensure_checkpoint_bundled_but_missing_raises(tmp_path):
    assert "tiny" in BUNDLED_CHECKPOINTS
    with pytest.raises(CheckpointDownloadError):
        ensure_checkpoint(tmp_path, "tiny")


def test_ensure_checkpoint_returns_existing_file_without_download(tmp_path, monkeypatch):
    path = checkpoint_path(tmp_path, "small")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"dummy weights")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("urlretrieve should not be called when file already exists")

    monkeypatch.setattr("urllib.request.urlretrieve", _fail_if_called)

    result = ensure_checkpoint(tmp_path, "small")
    assert result == path


def test_ensure_checkpoint_downloads_when_missing(tmp_path, monkeypatch):
    calls = []

    def _fake_urlretrieve(url, filename, reporthook=None):
        calls.append(url)
        if reporthook is not None:
            reporthook(1, 100, 100)
        from pathlib import Path

        Path(filename).write_bytes(b"fake model weights")

    monkeypatch.setattr("urllib.request.urlretrieve", _fake_urlretrieve)

    progress_events = []
    result = ensure_checkpoint(
        tmp_path, "large", progress_callback=lambda done, total: progress_events.append((done, total))
    )

    assert result.is_file()
    assert result.read_bytes() == b"fake model weights"
    assert len(calls) == 1
    assert "sam2_hiera_large.pt" in calls[0]
    assert progress_events == [(100, 100)]
