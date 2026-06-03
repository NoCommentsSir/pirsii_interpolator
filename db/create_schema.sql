CREATE SCHEMA IF NOT EXISTS video_interpolation;

CREATE TABLE IF NOT EXISTS  video_interpolation.input_videos(
    video_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    staged_video_uri VARCHAR NOT NULL,
    validation_status VARCHAR NOT NULL,
    validation_error_code VARCHAR NULL,
    queue_status VARCHAR NOT NULL,
    duration_sec INT NOT NULL,
    file_size_mb INT NOT NULL,
    width INT NULL,
    height INT NULL,
    fps FLOAT NULL,
    codec VARCHAR NULL,
    bitrate INT NULL,
    processed_at TIMESTAMP NULL,
    output_video_uri VARCHAR NULL,
    quality_metrics_summary JSONB NULL,
    coef INT NOT NULL,

    CONSTRAINT chk_file_size_mb CHECK (file_size_mb < 10),
    CONSTRAINT chk_duration_sec CHECK (duration_sec < 15)
);

CREATE TABLE IF NOT EXISTS  video_interpolation.online_metrics(
    metric_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    video_id INT NOT NULL,
    model_version VARCHAR NOT NULL,
    interpolation_factor INT NOT NULL,
    duration_seconds FLOAT NULL,
    clip_score_psnr FLOAT NULL,
    clip_score_ssim FLOAT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    FOREIGN KEY (video_id) REFERENCES video_interpolation.input_videos(video_id) ON DELETE CASCADE
);
