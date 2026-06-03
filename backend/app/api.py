import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
from sqlalchemy.orm import Session
from datetime import timedelta

from db.database import get_db, get_minio_client, get_redis_client
from .schemas import VideoResponse
from .services import (
    create_video,
    get_video_by_id,
    create_redis_task,
    VideoStorageError,
    VideoPersistenceError,
    VideoServiceError,
    VideoValidationError
)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

load_dotenv()
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "videos")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "password")
MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", f"localhost:{os.getenv('MINIO_API_PORT', '9000')}")
MINIO_PUBLIC_SECURE = os.getenv("MINIO_PUBLIC_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"}
MINIO_REGION = os.getenv("MINIO_REGION", "us-east-1")
ALLOWED_COEFS = {2, 3, 4}

def _load_cors_origins() -> list[str]:
    origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if origins:
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

api = FastAPI(title="PirsiiInterpretator API")
Instrumentator().instrument(api).expose(api)
api.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _read_upload_bytes(file: UploadFile) -> bytes:
    try:
        file.file.seek(0)
        return file.file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read the uploaded file.",
        ) from exc

def _to_video_response(video, minio_client: Minio) -> VideoResponse:
    output_uri = video.output_video_uri
    download_uri = None

    if output_uri:
        try:
            bucket, object_name = str(output_uri).split("/", 1)
        except ValueError as exc:
            logging.exception("Invalid output_video_uri for video_id=%s", video.video_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid output video URI.",
            ) from exc

        if not bucket or not object_name:
            logging.error("Invalid output_video_uri for video_id=%s: %s", video.video_id, output_uri)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid output video URI.",
            )

        presign_client = Minio(
            endpoint=MINIO_PUBLIC_ENDPOINT,
            access_key=MINIO_ROOT_USER,
            secret_key=MINIO_ROOT_PASSWORD,
            secure=MINIO_PUBLIC_SECURE,
            region=MINIO_REGION,
        )
        download_uri = presign_client.presigned_get_object(
            bucket,
            object_name,
            expires=timedelta(seconds=3600),
        )

    return VideoResponse(
        video_id=video.video_id,
        staged_video_uri=video.staged_video_uri,
        validation_status=video.validation_status,
        queue_status=video.queue_status,
        output_video_uri=output_uri,
        video_installing_uri=download_uri,
    )

@api.post(
    "/api/videos",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
)
def insert_video(
    video: Annotated[UploadFile, File(...)],
    coef: Annotated[int, Form(description="Interpolation coefficient. Allowed values: 2, 3, 4.")] = 2,
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio_client),
    redis_client = Depends(get_redis_client)
):
    logging.info("Received request to insert video. Filename: %s, Content-Type: %s", video.filename, video.content_type)
    if coef not in ALLOWED_COEFS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Interpolation coefficient must be one of: 2, 3, 4.",
        )

    file_bytes = _read_upload_bytes(video)
    try:
        video_obj = create_video(
            db,
            minio,
            MINIO_BUCKET_NAME,
            file_bytes=file_bytes,
            name=video.filename,
            coef=coef
        )
    except VideoValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (VideoStorageError, VideoPersistenceError) as exc:
        raise HTTPException( 
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except VideoServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    create_redis_task(redis_client, video_obj.video_id)
    return _to_video_response(video_obj, minio)

@api.get(
    "/api/videos/{video_id}",
    response_model=VideoResponse,
    status_code=status.HTTP_200_OK,
)
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    minio_client: Minio = Depends(get_minio_client)
):
    video = get_video_by_id(db, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )
    return _to_video_response(video, minio_client)
