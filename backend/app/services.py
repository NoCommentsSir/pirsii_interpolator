from __future__ import annotations

import os
import subprocess
import io
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass
import uuid
from moviepy import VideoFileClip
from minio import Minio
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from dotenv import load_dotenv

from db.models import InputVideos, OnlineMetrics
from redis import Redis
from backend.worker.worker import process_video
import rq

load_dotenv()

MAX_FILE_SIZE_MB = 10
MAX_DURATION_SECONDS = 15
IGNORED_STORAGE_DELETE_ERRORS = {"NoSuchBucket", "NoSuchKey", "NoSuchObject", "NoSuchVersion"}
REDIS_TOPIC = os.getenv("REDIS_TOPIC", "interpolation_tasks")
REDIS_QUEUE_NAME = os.getenv("REDIS_QUEUE_NAME", "interpolation_tasks")

class VideoServiceError(Exception):
    """Base exception for video service failures."""


class VideoValidationError(VideoServiceError):
    """Raised when uploaded video fails validation checks."""


class VideoStorageError(VideoServiceError):
    """Raised when MinIO operations fail."""


class VideoPersistenceError(VideoServiceError):
    """Raised when database operations fail."""

@dataclass(slots=True)
class ParsedVideo:
    fps: float
    file_size_mb: int
    width: int
    height: int
    bitrate: int
    codec: str
    duration_sec: float
    name: str

def get_video_codec(path: str) -> str:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "json",
            path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)
    streams = data.get("streams", [])

    if not streams:
        return ""

    return streams[0].get("codec_name", "")

def _parse_video_bytes(file_bytes: bytes, filename: str) -> ParsedVideo:
    ext = Path(filename).suffix.lower()
    if not file_bytes:
        raise VideoValidationError(f"Uploaded file is empty. {len(file_bytes)} bytes found.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        clip = VideoFileClip(filename=tmp_path)
        fps = clip.fps
        width, height = clip.size
        duration_sec = clip.duration
        file_size_mb = len(file_bytes) // (1024 * 1024)
        bitrate = int(clip.reader.bitrate) if clip.reader and clip.reader.bitrate else 0
        codec = get_video_codec(tmp_path)
        name = filename
        clip.close()
    except Exception as exc:
        raise VideoValidationError(f"Uploaded file is not a valid video file. {str(exc)}") from exc

    if not fps or fps <= 0:
        raise VideoValidationError(f"Uploaded file has an invalid frame rate. {fps} fps found.")

    if file_size_mb > MAX_FILE_SIZE_MB:
        raise VideoValidationError(f"Uploaded file exceeds the maximum allowed size of {MAX_FILE_SIZE_MB} MB. {file_size_mb} MB found.")

    if duration_sec <= 0 or duration_sec > MAX_DURATION_SECONDS:
        raise VideoValidationError(f"Uploaded file has an invalid duration. {duration_sec} seconds found.")

    return ParsedVideo(fps=fps, file_size_mb=file_size_mb, width=width, height=height, bitrate=bitrate, codec=codec, duration_sec=duration_sec, name=name)

def _remove_object_quietly(minio: Minio, bucket_name: str, object_name: str) -> None:
    try:
        minio.remove_object(bucket_name, object_name)
    except Exception:
        return

def ensure_bucket_exists(minio: Minio, bucket_name: str) -> None:
    try:
        if not minio.bucket_exists(bucket_name):
            minio.make_bucket(bucket_name)
    except Exception as exc:
        raise VideoStorageError("Failed to prepare the object storage bucket.") from exc

def get_video_by_id(
    db: Session,
    id: int
) -> InputVideos:
    return db.query(InputVideos).filter(InputVideos.video_id == id).first()

def create_video(
    db: Session,
    minio: Minio,
    bucket_name: str,
    file_bytes: bytes,
    name: str,
    coef: int
) -> InputVideos:
    minio_name = uuid.uuid4().hex + Path(name).suffix
    parsed_video = _parse_video_bytes(file_bytes, minio_name)
    ensure_bucket_exists(minio, bucket_name)
    minio_key = f"input/{parsed_video.name}"

    try:
        minio.put_object(
            bucket_name=bucket_name,
            object_name=minio_key,
            data=io.BytesIO(file_bytes),
            length=len(file_bytes),
            content_type="video/mp4",
        )
    except Exception as exc:
        raise VideoStorageError("Failed to upload the video.") from exc

    try:
        video = InputVideos(
            uploaded_at=datetime.now(timezone.utc),
            staged_video_uri=f"{bucket_name}/{minio_key}",
            validation_status="valid",
            validation_error_code=None,
            queue_status="pending",
            duration_sec=int(parsed_video.duration_sec),
            file_size_mb=parsed_video.file_size_mb,
            width=parsed_video.width,
            height=parsed_video.height,
            fps=parsed_video.fps,
            codec=parsed_video.codec,
            bitrate=parsed_video.bitrate,
            processed_at=None,
            output_video_uri=None,
            quality_metrics_summary=None,
            coef=coef
        )
        db.add(video)
        db.flush()
        db.commit()
        db.refresh(video)
        return video
    except Exception as exc:
        db.rollback()
        _remove_object_quietly(minio, bucket_name, minio_key)
        raise VideoPersistenceError(f"Failed to save the video metadata. {str(exc)}") from exc
    
def create_redis_task(
    redis_client: Redis,
    video_id: int,
    output_playback_mode: str = "real_time",
    timeout_seconds: int = 300
):
    try:
        queue = rq.Queue("interpolation_tasks", connection=redis_client)
        queue.enqueue(process_video, video_id, output_playback_mode)
    except Exception as exc:
        raise VideoServiceError("Failed to create processing task in Redis.") from exc

if __name__ == "__main__":
    pass
 
