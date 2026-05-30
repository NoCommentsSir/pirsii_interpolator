import dotenv
import os

from minio import Minio
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker
import redis

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
dotenv.load_dotenv()
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "password")
MINIO_PORT = os.getenv("MINIO_API_PORT", "9000")
MINIO_HOST = os.getenv("MINIO_HOST", "minio_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "pg_db")
POSTGRES_DB = os.getenv("POSTGRES_DB", "video_interpolation")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "videos")

# Log MinIO connection details
logger = logging.getLogger(__name__)
minio_endpoint = f"{MINIO_HOST}:{MINIO_PORT}"
logger.info(f"Initializing MinIO client with endpoint: {minio_endpoint}")

minio_client = Minio(
    endpoint=minio_endpoint,
    access_key=MINIO_ROOT_USER,
    secret_key=MINIO_ROOT_PASSWORD,
    secure=False
)

pg_link = URL.create(
    "postgresql+psycopg2",
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    host=POSTGRES_HOST,
    port=int(POSTGRES_PORT),
    database=POSTGRES_DB,
)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis_db"), 
    port=int(os.getenv("REDIS_PORT", "6379")), 
    db=0
)

pg_engine = create_engine(pg_link, pool_size=20, max_overflow=20, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_minio_client() -> Minio:
    return minio_client

def get_redis_client() -> redis.Redis:
    return redis_client

if __name__ == '__main__':
    pass
