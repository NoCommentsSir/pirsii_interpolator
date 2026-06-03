from sqlalchemy import Column, Float, Integer, ForeignKey, TIMESTAMP, JSON, VARCHAR, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class InputVideos(Base):
    __tablename__ = "input_videos"
    __table_args__ = {"schema": "video_interpolation"}
    video_id = Column(Integer, primary_key=True, autoincrement=True) 
    uploaded_at = Column(TIMESTAMP, nullable=False)
    staged_video_uri = Column(VARCHAR, nullable=False)
    validation_status = Column(VARCHAR, nullable=False)
    validation_error_code = Column(VARCHAR, nullable=True)
    queue_status = Column(VARCHAR, nullable=False)
    duration_sec = Column(Integer, nullable=False)
    file_size_mb = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    codec = Column(VARCHAR, nullable=True)
    bitrate = Column(Integer, nullable=True)
    processed_at = Column(TIMESTAMP, nullable=True)
    output_video_uri = Column(VARCHAR, nullable=True)
    quality_metrics_summary = Column(JSON, nullable=True)
    coef = Column(Integer, nullable=False)

    metrics = relationship("OnlineMetrics", back_populates="video", passive_deletes=True)

class OnlineMetrics(Base):
    __tablename__ = "online_metrics"
    __table_args__ = {"schema": "video_interpolation"}
    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("video_interpolation.input_videos.video_id"), nullable=False)
    model_version = Column(VARCHAR, nullable=False)
    interpolation_factor = Column(Integer, nullable=False)
    pairs_processed = Column(Integer, nullable=True)
    frames_wrtitten = Column(Integer, nullable=True)
    clip_score_psnr = Column(Float, nullable=True)
    clip_score_ssim = Column(Float, nullable=True)
    quality_frames_wrtitten = Column(Integer, nullable=True)
    bad_triplet_count = Column(Integer, nullable=True)
    is_bad_request = Column(Boolean, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False)

    video = relationship("InputVideos", back_populates="metrics")