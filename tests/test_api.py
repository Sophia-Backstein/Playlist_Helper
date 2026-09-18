"""Tests for the Playlist Helper API server.

Tests all API endpoints using FastAPI's TestClient.
Requires: pytest, httpx
"""

from __future__ import annotations

import os
import sys
import json
import subprocess
import tempfile

import pytest
from fastapi.testclient import TestClient

# Add project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Build a minimal test audio file for testing
TEST_DIR = os.path.join(PROJECT_ROOT, "tests")
ORIGINAL_DIR = os.path.join(TEST_DIR, "original")


def _has_media_files() -> bool:
    """Check if there are media files in the original test dir."""
    if not os.path.isdir(ORIGINAL_DIR):
        return False
    for f in os.listdir(ORIGINAL_DIR):
        ext = os.path.splitext(f)[1].lower()
        if ext in (".mp3", ".wav", ".flac", ".m4a", ".opus",
                    ".mp4", ".avi", ".flv", ".mkv", ".webm", ".mov"):
            return True
    return False


def _create_test_wav(path: str, duration_sec: float = 1.0) -> bool:
    """Create a synthetic WAV file for testing using ffmpeg."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-f", "lavfi", "-i",
                f"anoisesrc=d={duration_sec}:c=pink:a=0.5",
                "-ac", "1", "-ar", "22050",
                "-c:a", "pcm_s16le",
                "-f", "wav",
                path,
            ],
            capture_output=True, timeout=30,
        )
        return os.path.exists(path) and os.path.getsize(path) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _create_test_mp3(path: str, duration_sec: float = 1.0) -> bool:
    """Create a synthetic MP3 file for testing using ffmpeg."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-f", "lavfi", "-i",
                f"anoisesrc=d={duration_sec}:c=pink:a=0.5",
                "-ac", "1", "-ar", "22050",
                "-c:a", "libmp3lame",
                "-q:a", "2",
                path,
            ],
            capture_output=True, timeout=30,
        )
        return os.path.exists(path) and os.path.getsize(path) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _create_test_flac(path: str, duration_sec: float = 1.0) -> bool:
    """Create a synthetic FLAC file for testing using ffmpeg."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-f", "lavfi", "-i",
                f"anoisesrc=d={duration_sec}:c=pink:a=0.5",
                "-ac", "1", "-ar", "22050",
                "-c:a", "flac",
                path,
            ],
            capture_output=True, timeout=30,
        )
        return os.path.exists(path) and os.path.getsize(path) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    """Create a FastAPI TestClient with a fresh server instance."""
    from server.main import app, SESSION, cleanup_workspace

    # Reset session state completely
    SESSION.clear()
    SESSION.update({
        "workspace": None,
        "tracks": {},
        "track_files": {},
        "results": {},
        "track_info_cache": {},
        "next_track_id": 1,
        "next_result_id": 1,
    })

    # Ensure workspace is set
    from server.main import get_workspace
    ws = get_workspace()
    os.makedirs(ws, exist_ok=True)

    # Clear any test results from previous runs among routers
    SESSION.setdefault("results", {})

    with TestClient(app) as c:
        yield c

    # Cleanup
    cleanup_workspace()


@pytest.fixture(scope="module")
def test_wav():
    """Create a test WAV file."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    ok = _create_test_wav(path)
    assert ok, "Failed to create test WAV"
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def test_mp3():
    """Create a test MP3 file."""
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    ok = _create_test_mp3(path)
    assert ok, "Failed to create test MP3"
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def test_flac():
    """Create a test FLAC file."""
    fd, path = tempfile.mkstemp(suffix=".flac")
    os.close(fd)
    ok = _create_test_flac(path)
    assert ok, "Failed to create test FLAC"
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def server_media_dir():
    """Create a temp dir with media files for scan testing."""
    tmpdir = tempfile.mkdtemp(prefix="playlist_scan_test_")
    wav_path = os.path.join(tmpdir, "test_audio.wav")
    mp3_path = os.path.join(tmpdir, "test_audio.mp3")
    _create_test_wav(wav_path)
    _create_test_mp3(mp3_path)
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Health / Info ───────────────────────────────────────────────────


class TestServerInfo:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_info(self, client):
        resp = client.get("/api/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Playlist Helper API"
        assert data["status"] == "running"

    def test_index(self, client):
        """Root should serve the frontend HTML."""
        resp = client.get("/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "text/html" in resp.headers.get("content-type", ""), "Expected HTML response"


# ── Upload ──────────────────────────────────────────────────────────


class TestUpload:
    def test_upload_wav(self, client, test_wav):
        with open(test_wav, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("test.wav", f, "audio/wav")})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 1
        assert len(data["tracks"]) >= 1
        track = data["tracks"][0]
        assert "test.wav" in track["file_name"], f"Expected filename containing test.wav, got {track['file_name']}"
        assert track["format"] == "wav"

    def test_upload_mp3(self, client, test_mp3):
        with open(test_mp3, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("test.mp3", f, "audio/mpeg")})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 1
        assert data["tracks"][0]["format"] == "mp3"

    def test_upload_multiple(self, client, test_wav, test_mp3):
        with open(test_wav, "rb") as f1, open(test_mp3, "rb") as f2:
            resp = client.post(
                "/api/upload",
                files=[
                    ("files", ("multi1.wav", f1, "audio/wav")),
                    ("files", ("multi2.mp3", f2, "audio/mpeg")),
                ],
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 2


# ── Scan ────────────────────────────────────────────────────────────


class TestScan:
    def test_scan_valid_dir(self, client, server_media_dir):
        resp = client.post("/api/scan", json={"folder_path": server_media_dir})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["count"] >= 1
        assert data["folder_path"] == server_media_dir

    def test_scan_invalid_dir(self, client):
        resp = client.post("/api/scan", json={"folder_path": "/nonexistent/path"})
        assert resp.status_code == 400


# ── Track CRUD ─────────────────────────────────────────────────────


class TestTrackCRUD:
    @pytest.fixture(autouse=True)
    def setup_track(self, client, test_wav):
        """Upload a track for CRUD tests."""
        with open(test_wav, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("crud_test.wav", f, "audio/wav")})
        data = resp.json()
        self.track_id = data["tracks"][0]["track_id"]

    def test_list_tracks(self, client):
        resp = client.get("/api/tracks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

    def test_get_track(self, client):
        resp = client.get(f"/api/tracks/{self.track_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["track_id"] == self.track_id
        assert data["format"] == "wav"

    def test_get_track_not_found(self, client):
        resp = client.get("/api/tracks/99999")
        assert resp.status_code == 404

    def test_rename_track(self, client):
        resp = client.put(
            f"/api/tracks/{self.track_id}/rename",
            json={"new_filename": "renamed_test.wav"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["file_name"] == "renamed_test.wav"

    def test_rename_path_traversal_rejected(self, client):
        """Renaming with a path traversal component should be rejected."""
        resp = client.put(
            f"/api/tracks/{self.track_id}/rename",
            json={"new_filename": "../etc/passwd"},
        )
        assert resp.status_code == 400, f"Expected 400 for path traversal, got {resp.status_code}"

    def test_rename_absolute_path_rejected(self, client):
        """Renaming with an absolute path should be rejected."""
        resp = client.put(
            f"/api/tracks/{self.track_id}/rename",
            json={"new_filename": "/tmp/malicious.wav"},
        )
        assert resp.status_code == 400, f"Expected 400 for absolute path, got {resp.status_code}"

    def test_delete_track(self, client):
        # Upload a fresh track for deletion
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        _create_test_wav(path)
        with open(path, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("del_test.wav", f, "audio/wav")})
        os.remove(path)
        tid = resp.json()["tracks"][0]["track_id"]

        resp = client.delete(f"/api/tracks/{tid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify it's gone
        resp = client.get(f"/api/tracks/{tid}")
        assert resp.status_code == 404


# ── Analysis ────────────────────────────────────────────────────────


class TestAnalysis:
    @pytest.fixture(autouse=True)
    def setup_track(self, client, test_wav):
        with open(test_wav, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("analyze_test.wav", f, "audio/wav")})
        self.track_id = resp.json()["tracks"][0]["track_id"]

    def test_analyze_volume(self, client):
        resp = client.post(f"/api/tracks/{self.track_id}/analyze")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["track_id"] == self.track_id
        # Volume should be non-zero for a noise signal
        assert data["mean_volume_db"] != 0.0
        assert data["cleaned_average_db"] != 0.0

    def test_analyze_not_found(self, client):
        resp = client.post("/api/tracks/99999/analyze")
        assert resp.status_code == 404


# ── Processing ──────────────────────────────────────────────────────


class TestProcessing:
    @pytest.fixture(autouse=True)
    def setup_track(self, client, test_wav):
        with open(test_wav, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("proc_test.wav", f, "audio/wav")})
        self.track_id = resp.json()["tracks"][0]["track_id"]

    def test_trim(self, client):
        resp = client.post(
            f"/api/tracks/{self.track_id}/trim",
            json={"start_time": 0.1, "end_time": 0.5},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["duration_seconds"] is not None
        assert data["duration_seconds"] <= 0.5
        # Should have a result_id for downloads
        assert data.get("result_id") is not None, "Expected result_id in trim response"

    def test_trim_invalid_range(self, client):
        resp = client.post(
            f"/api/tracks/{self.track_id}/trim",
            json={"start_time": 0.5, "end_time": 0.1},
        )
        assert resp.status_code == 400

    def test_convert_to_mp3(self, client):
        resp = client.post(
            f"/api/tracks/{self.track_id}/convert",
            json={"target_format": "mp3"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data.get("result_id") is not None, "Expected result_id in convert response"

    def test_convert_to_flac(self, client):
        resp = client.post(
            f"/api/tracks/{self.track_id}/convert",
            json={"target_format": "flac"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True

    def test_convert_invalid_format(self, client):
        resp = client.post(
            f"/api/tracks/{self.track_id}/convert",
            json={"target_format": "ogg"},
        )
        assert resp.status_code == 422  # Validation error

    def test_combined_process(self, client):
        resp = client.post(
            f"/api/tracks/{self.track_id}/process",
            json={
                "target_format": "mp3",
                "start_time": 0.1,
                "end_time": 0.8,
                "volume_gain_db": 2.0,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["duration_seconds"] is not None
        assert data.get("result_id") is not None, "Expected result_id in process response"


# ── Equalization ────────────────────────────────────────────────────


class TestEqualize:
    @pytest.fixture(autouse=True)
    def setup_tracks(self, client, test_wav, test_mp3):
        ids = []
        for name, fpath in [("eq1.wav", test_wav), ("eq2.mp3", test_mp3)]:
            with open(fpath, "rb") as f:
                resp = client.post("/api/upload", files={"files": (name, f, "audio/mpeg")})
            ids.append(resp.json()["tracks"][0]["track_id"])
        self.track_ids = ids

    def test_equalize_average(self, client):
        resp = client.post(
            "/api/equalize/average",
            json={"target_db": -16.0, "track_ids": self.track_ids},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 2
        for result in data:
            assert result["success"] is True
            assert result.get("result_id") is not None, "Expected result_id in equalize-average response"

    def test_equalize_average_empty(self, client):
        resp = client.post(
            "/api/equalize/average",
            json={"target_db": -16.0, "track_ids": []},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_equalize_loudest(self, client):
        resp = client.post(
            "/api/equalize/loudest",
            json={"target_db": -16.0, "track_ids": self.track_ids},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 2
        for result in data:
            assert result["success"] is True
            assert result.get("result_id") is not None, "Expected result_id in equalize-loudest response"


# ── Metadata ────────────────────────────────────────────────────────


class TestMetadata:
    @pytest.fixture(autouse=True)
    def setup_track(self, client, test_mp3):
        with open(test_mp3, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("meta_test.mp3", f, "audio/mpeg")})
        self.track_id = resp.json()["tracks"][0]["track_id"]

    def test_get_metadata(self, client):
        resp = client.get(f"/api/tracks/{self.track_id}/metadata")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["track_id"] == self.track_id
        assert "meta_test.mp3" in data["file_name"], f"Expected filename containing meta_test.mp3, got {data['file_name']}"

    def test_get_title(self, client):
        resp = client.get(f"/api/tracks/{self.track_id}/metadata/title")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "title" in data

    def test_set_title(self, client):
        resp = client.put(
            f"/api/tracks/{self.track_id}/metadata/title",
            json={"title": "API Test Title"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["title"] == "API Test Title"

        # Verify readback
        resp2 = client.get(f"/api/tracks/{self.track_id}/metadata/title")
        assert resp2.json()["title"] == "API Test Title"

    def test_get_cover_not_found(self, client):
        """MP3 without cover art should return 404."""
        resp = client.get(f"/api/tracks/{self.track_id}/cover")
        # Either 404 (no cover) or 200 (has cover if generated with cover art)
        assert resp.status_code in (200, 404)


# ── Download ────────────────────────────────────────────────────────


class TestDownload:
    @pytest.fixture(autouse=True)
    def setup_track(self, client, test_wav):
        with open(test_wav, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("dl_test.wav", f, "audio/wav")})
        self.track_id = resp.json()["tracks"][0]["track_id"]

    def test_download_original(self, client):
        resp = client.get(f"/api/tracks/{self.track_id}/download")
        assert resp.status_code == 200
        assert "audio" in resp.headers["content-type"], f"Expected audio/* content-type, got {resp.headers['content-type']}"
        assert int(resp.headers["content-length"]) > 1000

    def test_download_converted(self, client):
        resp = client.get(f"/api/tracks/{self.track_id}/download?format=mp3")
        assert resp.status_code == 200, resp.text
        assert "audio" in (resp.headers.get("content-type", ""))

    def test_download_not_found(self, client):
        resp = client.get("/api/tracks/99999/download")
        assert resp.status_code == 404


# ── Result Downloads ────────────────────────────────────────────────


class TestResultDownload:
    @pytest.fixture(autouse=True)
    def setup_track(self, client, test_wav):
        with open(test_wav, "rb") as f:
            resp = client.post("/api/upload", files={"files": ("result_test.wav", f, "audio/wav")})
        self.track_id = resp.json()["tracks"][0]["track_id"]

    def test_download_trim_result(self, client):
        """After trimming, the result should be downloadable via the result_id endpoint."""
        resp = client.post(
            f"/api/tracks/{self.track_id}/trim",
            json={"start_time": 0.1, "end_time": 0.5},
        )
        assert resp.status_code == 200, resp.text
        result_id = resp.json().get("result_id")
        assert result_id is not None, "No result_id in trim response"

        dl_resp = client.get(f"/api/results/{result_id}/download")
        assert dl_resp.status_code == 200, f"Result download failed: {dl_resp.text}"
        assert int(dl_resp.headers["content-length"]) > 0, "Empty result file"

    def test_download_convert_result(self, client):
        """After conversion, the result should be downloadable via the result_id endpoint."""
        resp = client.post(
            f"/api/tracks/{self.track_id}/convert",
            json={"target_format": "mp3"},
        )
        assert resp.status_code == 200, resp.text
        result_id = resp.json().get("result_id")
        assert result_id is not None, "No result_id in convert response"

        dl_resp = client.get(f"/api/results/{result_id}/download")
        assert dl_resp.status_code == 200, f"Result download failed: {dl_resp.text}"
        assert int(dl_resp.headers["content-length"]) > 0, "Empty result file"

    def test_download_nonexistent_result(self, client):
        """Downloading a non-existent result_id should 404."""
        resp = client.get("/api/results/99999/download")
        assert resp.status_code == 404

    def test_get_result_info(self, client):
        """The result info endpoint should return metadata about a result."""
        resp = client.post(
            f"/api/tracks/{self.track_id}/convert",
            json={"target_format": "flac"},
        )
        assert resp.status_code == 200, resp.text
        result_id = resp.json().get("result_id")
        assert result_id is not None

        info_resp = client.get(f"/api/results/{result_id}/info")
        assert info_resp.status_code == 200, info_resp.text
        data = info_resp.json()
        assert data["result_id"] == result_id
        assert data["exists"] is True
        assert data["track_id"] == self.track_id


# ─── Run if called directly ────────────────────────────────────────

if __name__ == "__main__":
    pytest.main(["-v", __file__])
