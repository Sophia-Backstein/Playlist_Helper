"""Pydantic models for Playlist Helper API request/response schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class TrackInfo(BaseModel):
    """Information about a single track in the session."""
    track_id: str
    file_name: str
    file_path: str
    duration_seconds: float = 0.0
    format: str = "mp3"
    media_type: str = "audio"
    title: str = ""
    average_volume_db: float = 0.0
    cleaned_average_db: float = 0.0
    max_volume_db: float = 0.0
    has_cover: bool = False
    size_bytes: int = 0


class TrackListResponse(BaseModel):
    """Response listing all tracks in the session."""
    tracks: list[TrackInfo]
    count: int


class ScanRequest(BaseModel):
    """Request to scan a folder for media files."""
    folder_path: str


class ScanResponse(BaseModel):
    """Response from a folder scan."""
    tracks: list[TrackInfo]
    count: int
    folder_path: str


class AnalyzeResponse(BaseModel):
    """Volume analysis result for a single track."""
    track_id: str
    mean_volume_db: float
    max_volume_db: float
    cleaned_average_db: float
    loudest_average_db: float


class TrimRequest(BaseModel):
    """Request to trim a track."""
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)


class ConvertRequest(BaseModel):
    """Request to convert a track to a different format."""
    target_format: str = Field(pattern=r"^(mp3|wav|flac)$")


class ProcessRequest(BaseModel):
    """Combined trim + convert + volume gain request."""
    target_format: str = Field(default="mp3", pattern=r"^(mp3|wav|flac)$")
    start_time: float = Field(default=0.0, ge=0.0)
    end_time: Optional[float] = None
    volume_gain_db: Optional[float] = None


class EqualizeAverageRequest(BaseModel):
    """Request to equalize multiple tracks to a target average volume."""
    target_db: float = Field(default=-16.0)
    track_ids: list[str]


class EqualizeLoudestRequest(BaseModel):
    """Request to equalize multiple tracks based on loudest average."""
    target_db: float = Field(default=-16.0)
    track_ids: list[str]


class SetTitleRequest(BaseModel):
    """Request to set the title metadata on a track."""
    title: str


class RenameRequest(BaseModel):
    """Request to rename a track's file."""
    new_filename: str


class EqualizeResult(BaseModel):
    """Result of equalizing a single track."""
    track_id: str
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    result_id: Optional[str] = None


class ProcessResult(BaseModel):
    """Result of a processing operation on a track."""
    track_id: str
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    result_id: Optional[str] = None


class InfoResponse(BaseModel):
    """Server info response."""
    name: str = "Playlist Helper API"
    version: str = "1.0.0"
    status: str = "running"
