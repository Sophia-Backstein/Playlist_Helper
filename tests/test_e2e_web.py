"""End-to-end web UI tests for Playlist Helper.

Tests every API endpoint and web UI surface that the frontend uses.
Simulates real user flows through the browser-facing API.
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
import wave
from pathlib import Path

import pytest
import requests

BASE_URL = "http://localhost:9999"
API = f"{BASE_URL}/api"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_wav():
    """Create a tiny valid WAV file for testing."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        # 2 seconds of silence
        w.writeframes(struct.pack("<h", 0) * 44100)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def test_mp3():
    """Create a minimal MP3-like file (not a real MP3, but tests upload)."""
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    # Minimal valid-ish MP3 frame
    with open(path, "wb") as f:
        # MPEG1 Audio Layer 3 frame header: sync + bitrate/sampling rate
        f.write(b"\xff\xfb\x90\x00" + b"\x00" * 400)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def test_jpg():
    """Create a tiny JPEG file for cover art testing."""
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    # Minimal JPEG (SOI + EOI markers with some data)
    with open(path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f\x1a9\x8b\x9d\x8b\xa7\x89\x88\xc6\xdd\xcd\xcc\xcd\xff\xdb\x00C\x01\x07\x07\x08\x08\x08\x10\x0c\x0c\x10\x1a\x0f\x0f\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x00\x00\x01\x02\x03\x11\x04\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04\x00\x01\x02w\x00\x01\x02\x03\x11\x04\x12!1\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08\x14#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xd9")
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="module")
def uploaded_tracks(test_wav, test_mp3):
    """Upload test files and return the track IDs."""
    resp = requests.post(
        f"{API}/upload",
        files=[
            ("files", ("test.wav", open(test_wav, "rb"), "audio/wav")),
            ("files", ("test.mp3", open(test_mp3, "rb"), "audio/mpeg")),
        ],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    tracks = {t["format"]: t["track_id"] for t in data["tracks"]}
    return tracks


# ── Health / Info Tests ──────────────────────────────────────────────


class TestServerHealth:
    def test_health_endpoint(self):
        resp = requests.get(f"{API}/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_info(self):
        resp = requests.get(f"{API}/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert "Playlist Helper" in data["name"]

    def test_index_html_served(self):
        resp = requests.get(f"{BASE_URL}/")
        assert resp.status_code == 200
        html = resp.text
        assert "Playlist Helper" in html
        assert "app.js" in html
        assert "style.css" in html

    def test_static_js_served(self):
        resp = requests.get(f"{BASE_URL}/static/js/app.js")
        assert resp.status_code == 200
        assert "API_BASE" in resp.text

    def test_static_css_served(self):
        resp = requests.get(f"{BASE_URL}/static/css/style.css")
        assert resp.status_code == 200
        assert "app-header" in resp.text


# ── Upload & Track Management Tests ─────────────────────────────────


class TestUploadAndTracks:
    def test_upload_multiple(self, test_wav):
        """Simulate dragging multiple files onto the upload zone."""
        resp = requests.post(
            f"{API}/upload",
            files=[
                ("files", ("a.wav", open(test_wav, "rb"), "audio/wav")),
                ("files", ("b.wav", open(test_wav, "rb"), "audio/wav")),
            ],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["tracks"]) == 2

    def test_unsupported_format_rejected(self):
        """Upload a .txt file — should be silently skipped (frontend filters too)."""
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with open(path, "w") as f:
            f.write("not audio")
        try:
            resp = requests.post(
                f"{API}/upload",
                files=[("files", ("test.txt", open(path, "rb"), "text/plain"))],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 0
        finally:
            os.remove(path)

    def test_list_tracks(self, uploaded_tracks):
        """Simulate frontend loading track list on page load."""
        resp = requests.get(f"{API}/tracks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        track_ids = {t["track_id"] for t in data["tracks"]}
        assert uploaded_tracks["wav"] in track_ids

    def test_get_single_track(self, uploaded_tracks):
        """Simulate clicking on a track in the sidebar."""
        tid = uploaded_tracks["wav"]
        resp = requests.get(f"{API}/tracks/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track_id"] == tid
        assert data["format"] == "wav"
        assert data["file_name"].endswith(".wav")
        assert data["duration_seconds"] >= 0
        assert "file_path" in data
        assert "media_type" in data
        assert "has_cover" in data

    def test_get_track_not_found(self):
        resp = requests.get(f"{API}/tracks/nonexistent")
        assert resp.status_code == 404

    def _upload_one_wav(self) -> str:
        """Upload a single WAV and return its track_id."""
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(struct.pack("<h", 0) * 22050)
        try:
            resp = requests.post(
                f"{API}/upload",
                files=[("files", ("tmp.wav", open(path, "rb"), "audio/wav"))],
            )
            assert resp.status_code == 200
            return resp.json()["tracks"][0]["track_id"]
        finally:
            os.remove(path)

    def test_delete_track(self):
        """Simulate clicking delete on a track."""
        tid = self._upload_one_wav()
        resp = requests.delete(f"{API}/tracks/{tid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify it's gone
        resp = requests.get(f"{API}/tracks/{tid}")
        assert resp.status_code == 404

    def test_rename_track(self):
        """Simulate renaming a file in the Info tab."""
        tid = self._upload_one_wav()
        new_name = f"renamed_{tid}.wav"
        resp = requests.put(
            f"{API}/tracks/{tid}/rename",
            json={"new_filename": new_name},
        )
        assert resp.status_code == 200, f"Rename failed: {resp.text}"
        data = resp.json()
        assert data["file_name"] == new_name

        # Verify UI would show new name
        resp = requests.get(f"{API}/tracks/{tid}")
        assert resp.json()["file_name"] == new_name

    def test_rename_path_traversal_rejected(self):
        tid = self._upload_one_wav()
        resp = requests.put(
            f"{API}/tracks/{tid}/rename",
            json={"new_filename": "../../etc/passwd"},
        )
        assert resp.status_code == 400

    def test_clear_single_track_workflow(self):
        """Simulate deleting a single uploaded track."""
        tid = self._upload_one_wav()
        resp = requests.delete(f"{API}/tracks/{tid}")
        assert resp.status_code == 200
        resp = requests.get(f"{API}/tracks/{tid}")
        assert resp.status_code == 404


# ── Volume Analysis Tests ────────────────────────────────────────────


class TestVolumeAnalysis:
    def test_analyze_volume(self, uploaded_tracks):
        """Simulate clicking 'Analyze Volume' button."""
        tid = uploaded_tracks["wav"]
        resp = requests.post(f"{API}/tracks/{tid}/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track_id"] == tid
        assert isinstance(data["mean_volume_db"], float)
        assert isinstance(data["cleaned_average_db"], float)
        assert isinstance(data["max_volume_db"], float)

    def test_analyze_nonexistent(self):
        resp = requests.post(f"{API}/tracks/nonexistent/analyze")
        assert resp.status_code == 404


# ── Trim Tests ───────────────────────────────────────────────────────


class TestTrim:
    def test_trim_track(self, uploaded_tracks):
        """Simulate trim in the Trim tab."""
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/trim",
            json={"start_time": 0, "end_time": 0.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result_id"] is not None
        assert data["duration_seconds"] <= 0.6  # Allow some ffmpeg slop

    def test_trim_invalid_range(self, uploaded_tracks):
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/trim",
            json={"start_time": 1, "end_time": 0.5},
        )
        assert resp.status_code == 400


# ── Convert Tests ────────────────────────────────────────────────────


class TestConvert:
    def test_convert_to_mp3(self, uploaded_tracks):
        """Simulate converting in the Convert tab."""
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/convert",
            json={"target_format": "mp3"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result_id"] is not None

    def test_convert_to_flac(self, uploaded_tracks):
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/convert",
            json={"target_format": "flac"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_convert_invalid_format(self, uploaded_tracks):
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/convert",
            json={"target_format": "ogg"},
        )
        assert resp.status_code == 422  # Validation error


# ── Combined Process Tests ───────────────────────────────────────────


class TestProcess:
    def test_combined_process(self, uploaded_tracks):
        """Simulate the Process tab — trim + convert + gain."""
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/process",
            json={
                "target_format": "mp3",
                "start_time": 0,
                "end_time": 0.5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result_id"] is not None

    def test_process_with_gain(self, uploaded_tracks):
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/process",
            json={
                "target_format": "wav",
                "start_time": 0,
                "end_time": 0.5,
                "volume_gain_db": 2.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ── Metadata Tests ───────────────────────────────────────────────────


class TestMetadata:
    def test_get_title(self, uploaded_tracks):
        """Simulate reading title in the Info tab."""
        tid = uploaded_tracks["wav"]
        resp = requests.get(f"{API}/tracks/{tid}/metadata/title")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track_id"] == tid

    def test_set_title(self, uploaded_tracks):
        """Simulate editing title and clicking Save."""
        tid = uploaded_tracks["wav"]
        resp = requests.put(
            f"{API}/tracks/{tid}/metadata/title",
            json={"title": "E2E Test Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify it persisted
        resp = requests.get(f"{API}/tracks/{tid}/metadata/title")
        assert resp.json()["title"] == "E2E Test Title"

    def test_get_all_metadata(self, uploaded_tracks):
        """Simulate the Metadata tab's refresh button."""
        tid = uploaded_tracks["wav"]
        resp = requests.get(f"{API}/tracks/{tid}/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track_id"] == tid
        assert "file_name" in data
        assert "title" in data
        assert "has_cover" in data
        assert "format" in data

    def test_get_cover_not_found(self, uploaded_tracks):
        """WAV files don't have embedded cover art."""
        tid = uploaded_tracks["wav"]
        resp = requests.get(f"{API}/tracks/{tid}/cover")
        assert resp.status_code == 404


# ── Stream (Playback) Tests ──────────────────────────────────────────


class TestStream:
    def test_stream_returns_audio(self, uploaded_tracks):
        """Simulate the Playback tab loading the audio source."""
        tid = uploaded_tracks["wav"]
        resp = requests.get(f"{API}/tracks/{tid}/stream")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "audio" in ct
        assert resp.headers.get("accept-ranges") == "bytes"

    def test_stream_nonexistent(self):
        resp = requests.get(f"{API}/tracks/nonexistent/stream")
        assert resp.status_code == 404


# ── Download Tests ───────────────────────────────────────────────────


class TestDownload:
    def test_download_original(self, uploaded_tracks):
        """Simulate clicking Download in the Info tab."""
        tid = uploaded_tracks["wav"]
        resp = requests.get(f"{API}/tracks/{tid}/download")
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert ".wav" in cd
        assert len(resp.content) > 0

    def test_download_converted(self, uploaded_tracks):
        """Download with format conversion."""
        tid = uploaded_tracks["wav"]
        resp = requests.get(f"{API}/tracks/{tid}/download?format=mp3")
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert ".mp3" in cd

    def test_download_not_found(self):
        resp = requests.get(f"{API}/tracks/nonexistent/download")
        assert resp.status_code == 404


# ── Results Tests ────────────────────────────────────────────────────


class TestResults:
    def _do_trim(self, uploaded_tracks) -> str:
        """Helper: perform a trim and return the result_id."""
        tid = uploaded_tracks["wav"]
        resp = requests.post(
            f"{API}/tracks/{tid}/trim",
            json={"start_time": 0, "end_time": 0.3},
        )
        return resp.json()["result_id"]

    def test_download_result(self, uploaded_tracks):
        """Simulate clicking a result download link in the frontend."""
        rid = self._do_trim(uploaded_tracks)
        resp = requests.get(f"{API}/results/{rid}/download")
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "filename" in cd
        assert len(resp.content) > 0

    def test_get_result_info(self, uploaded_tracks):
        rid = self._do_trim(uploaded_tracks)
        resp = requests.get(f"{API}/results/{rid}/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["result_id"] == rid
        assert data["operation"] == "trim"
        assert data["exists"] is True

    def test_nonexistent_result(self):
        resp = requests.get(f"{API}/results/nonexistent/download")
        assert resp.status_code == 404

    def test_download_twice(self, uploaded_tracks):
        """Result download is single-use — second download should 404."""
        rid = self._do_trim(uploaded_tracks)
        resp1 = requests.get(f"{API}/results/{rid}/download")
        assert resp1.status_code == 200

        resp2 = requests.get(f"{API}/results/{rid}/download")
        assert resp2.status_code == 404


# ── Batch Equalize Tests ─────────────────────────────────────────────


class TestEqualize:
    def _upload_two(self):
        """Upload two WAV files for batch equalization."""
        tracks = []
        for _ in range(2):
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with wave.open(path, "w") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                w.writeframes(struct.pack("<h", 0) * 22050)
            try:
                resp = requests.post(
                    f"{API}/upload",
                    files=[("files", (os.path.basename(path), open(path, "rb"), "audio/wav"))],
                )
                if resp.status_code == 200:
                    tracks.extend(resp.json()["tracks"])
            finally:
                os.remove(path)
        return [t["track_id"] for t in tracks[:2]]

    def test_equalize_average(self):
        """Simulate 'Equalize to Average' batch button."""
        ids = self._upload_two()
        if len(ids) < 2:
            pytest.skip("Need at least 2 tracks")
        resp = requests.post(
            f"{API}/equalize/average",
            json={"target_db": -16.0, "track_ids": ids},
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2
        for r in results:
            assert r["success"] is True
            assert r["result_id"] is not None

    def test_equalize_loudest(self):
        ids = self._upload_two()
        if len(ids) < 2:
            pytest.skip("Need at least 2 tracks")
        resp = requests.post(
            f"{API}/equalize/loudest",
            json={"target_db": -16.0, "track_ids": ids},
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        for r in results:
            if r["success"]:
                assert r["result_id"] is not None

    def test_equalize_nonexistent_track(self):
        resp = requests.post(
            f"{API}/equalize/average",
            json={"target_db": -16.0, "track_ids": ["nonexistent"]},
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "not found" in results[0]["error"].lower()


# ── Web UI HTML Structure Tests ──────────────────────────────────────


class TestWebUIStructure:
    def test_index_has_all_tab_buttons(self):
        """Verify the frontend HTML includes all tab buttons the user needs."""
        resp = requests.get(f"{BASE_URL}/")
        html = resp.text
        tabs = ["tab-info", "tab-volume", "tab-trim", "tab-convert", "tab-process", "tab-playback", "tab-metadata"]
        for tab in tabs:
            assert tab in html, f"Missing tab: {tab}"

    def test_index_has_upload_zone(self):
        resp = requests.get(f"{BASE_URL}/")
        html = resp.text
        assert "upload-zone" in html
        assert "file-input" in html

    def test_index_has_download_and_results(self):
        resp = requests.get(f"{BASE_URL}/")
        html = resp.text
        assert "results-area" in html
        assert "clear-results" in html

    def test_index_has_batch_bar(self):
        resp = requests.get(f"{BASE_URL}/")
        html = resp.text
        assert "batch-bar" in html
        assert "eq-avg-btn" in html
        assert "eq-loud-btn" in html

    def test_index_has_scan_and_clear(self):
        resp = requests.get(f"{BASE_URL}/")
        html = resp.text
        assert "scan-btn" in html
        assert "clear-tracks" in html


# ── Error Handling Tests ─────────────────────────────────────────────


class TestErrorHandling:
    def test_upload_exceeds_max_size(self):
        """413 on too-large upload."""
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            # Write 501 MB of zeros
            with open(path, "wb") as f:
                f.write(b"\x00" * (501 * 1024 * 1024))
            resp = requests.post(
                f"{API}/upload",
                files=[("files", ("big.wav", open(path, "rb"), "audio/wav"))],
            )
            assert resp.status_code == 413
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_invalid_json_body_returns_422(self, uploaded_tracks):
        tid = uploaded_tracks["wav"]
        resp = requests.put(
            f"{API}/tracks/{tid}/metadata/title",
            json={},  # Missing 'title' field
        )
        assert resp.status_code == 422

    def test_track_not_found_for_all_operations(self):
        ops = [
            ("GET", f"{API}/tracks/nonexistent", None),
            ("DELETE", f"{API}/tracks/nonexistent", None),
            ("POST", f"{API}/tracks/nonexistent/analyze", None),
            ("POST", f"{API}/tracks/nonexistent/trim", {"start_time": 0, "end_time": 1}),
            ("POST", f"{API}/tracks/nonexistent/convert", {"target_format": "mp3"}),
            ("PUT", f"{API}/tracks/nonexistent/rename", {"new_filename": "x.wav"}),
        ]
        for method, url, body in ops:
            if method == "GET":
                resp = requests.get(url)
            elif method == "DELETE":
                resp = requests.delete(url)
            elif method == "PUT":
                resp = requests.put(url, json=body)
            else:
                resp = requests.post(url, json=body)
            assert resp.status_code == 404, f"{method} {url} expected 404, got {resp.status_code}"
