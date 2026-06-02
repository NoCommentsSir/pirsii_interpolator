import os, io
from dotenv import load_dotenv
import logging

from db.database import redis_client, SessionLocal, get_minio_client
from sqlalchemy.orm import Session
from db.models import InputVideos
from datetime import datetime, timezone
import rq
from rq.worker import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


load_dotenv()
REDIS_TOPIC = os.getenv("REDIS_TOPIC", "interpolation_tasks")
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "video")
QUEUE_NAME = os.getenv("REDIS_QUEUE_NAME", "interpolation_tasks")
q = rq.Queue(connection=redis_client)

def processor(video_obj: InputVideos, minio_client) -> str:
    try:
        minio_uri = video_obj.staged_video_uri
        minio_key = minio_uri.split("/", 1)[1]
        video_name = minio_key.split("/", 1)[1]
        logger.info(f"Processing video ID {video_obj.video_id} with interpolation factor {video_obj.coef}")
        interpolation_factor = video_obj.coef
        input_file = minio_client.get_object(BUCKET_NAME, minio_key)
        output_file = input_file.read() # ОЧЕВИДНО МЕНЯЕМ, ДОЛЖЕН ВЫЗЫВАТЬСЯ СЕВРИС МИНИО!
        logger.info(f"Video ID {video_obj.video_id} read from MinIO, size: {len(output_file)} bytes")
        minio_client.put_object(
            bucket_name=BUCKET_NAME,
            object_name=f'output/{video_name}.mp4',
            data=io.BytesIO(output_file),
            length=len(output_file),
            content_type="video/mp4",
        )
        return f'output/{video_name}.mp4'
    except Exception as e:
        print(f"Error processing video ID {video_obj.video_id}: {str(e)}")
        return None
    
def process_video(video_id: int):
    minio_client = get_minio_client()
    db = SessionLocal()
    try:
        video_obj = db.query(InputVideos).filter(InputVideos.video_id == video_id).first()
        if video_obj and video_obj.queue_status == "pending":
            video_obj.queue_status = "processing"
            db.commit()
            result = processor(video_obj, minio_client)
            if result:
                video_obj.processed_at = datetime.now(timezone.utc)
                video_obj.output_video_uri = f"{BUCKET_NAME}/{result}"
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