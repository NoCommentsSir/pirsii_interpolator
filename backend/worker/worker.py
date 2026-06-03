import os
import tempfile
import logging
from pathlib import Path

from dotenv import load_dotenv
from minio import Minio
from db.database import redis_client, SessionLocal, get_minio_client
from sqlalchemy.orm import Session
from db.models import InputVideos, OnlineMetrics
from datetime import datetime, timezone
import rq
from rq.worker import Worker

from .rife_client import call_rife_inference

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


load_dotenv()
REDIS_TOPIC = os.getenv("REDIS_TOPIC", "interpolation_tasks")
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "videos")
QUEUE_NAME = os.getenv("REDIS_QUEUE_NAME", "interpolation_tasks")
q = rq.Queue(connection=redis_client)

def processor(video_obj: InputVideos, minio_client: Minio, db: Session, output_playback_mode: str = "real_time") -> str | None:
    try:
        minio_uri = video_obj.staged_video_uri
        bucket_name, minio_key = minio_uri.split("/", 1)
        video_name = Path(minio_key).name
        logger.info(
            "Processing video ID %s with interpolation factor %s and playback mode %s",
            video_obj.video_id,
            video_obj.coef,
            output_playback_mode,
        )
        logger.info(
            "Processing video ID %s with interpolation factor %s and playback mode %s",
            video_obj.video_id,
            video_obj.coef,
            output_playback_mode,
        )
        interpolation_factor = video_obj.coef

        logger.info(f"Video ID {video_obj.video_id} read from MinIO and will be sent to BentoML")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / video_name
            output_path = tmp_path / f"{input_path.stem}_interpolated{input_path.suffix}"

            with minio_client.get_object(bucket_name, minio_key) as input_file:
                with open(input_path, "wb") as f:
                    f.write(input_file.read())

            response = call_rife_inference(str(input_path), str(output_path), interpolation_factor)
            db.add(OnlineMetrics(
                video_id=video_obj.video_id,
                model_version='RIFE_v1',
                interpolation_factor=response.get("interpolation_factor", interpolation_factor),
                pairs_processed=response.get("pairs_processed", None),
                frames_wrtitten=response.get("frames_wrtitten", None),
                clip_score_psnr=response.get("quality_psnr_mean", None),
                clip_score_ssim=response.get("quality_ssim_mean", None),
                quality_frames_wrtitten=response.get("quality_frames_wrtitten", None),
                bad_triplet_count=response.get("bad_triplet_count", None),
                is_bad_request=response.get("quality_error", None),
                created_at=datetime.now(timezone.utc)
            ))
            db.commit() 

            if not output_path.exists() or output_path.stat().st_size <= 0:
                raise RuntimeError(f"RIFE output file was not created: {output_path}")

            output_key = f"output/{output_path.name}"
            with open(output_path, "rb") as out_file:
                minio_client.put_object(
                    bucket_name=bucket_name,
                    object_name=output_key,
                    data=out_file,
                    length=os.path.getsize(output_path),
                    content_type="video/mp4",
                )

        return f"{bucket_name}/{output_key}"
    except Exception as e:
        logger.exception("Error processing video ID %s", video_obj.video_id)
        return None
    
def process_video(video_id: int, output_playback_mode: str = "real_time"):
    minio_client = get_minio_client()
    db = SessionLocal()
    try:
        video_obj = db.query(InputVideos).filter(InputVideos.video_id == video_id).first()
        if video_obj and video_obj.queue_status == "pending":
            video_obj.queue_status = "processing"
            db.commit()
            result = processor(video_obj, minio_client, output_playback_mode)
            result = processor(video_obj, minio_client, output_playback_mode)
            if result:
                video_obj.processed_at = datetime.now(timezone.utc)
                video_obj.output_video_uri = result
                video_obj.queue_status = "completed"
            else:
                video_obj.queue_status = "failed"
            db.commit()
        else:
            logger.warning(f"Video ID {video_id} not found or already processed.")
    finally:
        db.close()

def start_worker():
    """Start RQ Worker - автоматически обрабатывает job'ы из очереди"""
    queue = rq.Queue(QUEUE_NAME, connection=redis_client)
    worker = Worker([queue], connection=redis_client)
    logger.info(f"Starting RQ Worker for queue '{QUEUE_NAME}'")
    worker.work()

if __name__ == "__main__":
    start_worker()
