# Local Debugging and Manual Verification

This guide describes how to run and verify the local video interpolation flow without a real BentoML/RIFE service. Local mock inference copies the uploaded video to the output path after a short delay, so it verifies the backend, queue, worker, MinIO, polling, and download lifecycle without doing real interpolation.

## Services

The local Docker Compose stack starts:

- `pg-db`: PostgreSQL metadata database.
- `redis-db`: Redis broker for RQ jobs.
- `minio-db`: object storage for input and output videos.
- `backend`: FastAPI API on `http://localhost:8000`.
- `worker`: RQ worker that processes video jobs.
- `frontend`: production frontend container on `http://localhost:8080`.
- `prometheus`: metrics UI/API on `http://localhost:9090`.
- `grafana`: dashboard UI on `http://localhost:3000`.

## Environment

Create a local `.env` file:

```bash
cp .env.example .env
```

The default `.env.example` enables mock inference:

```env
RIFE_SERVICE_URL=mock://local
RIFE_MOCK_DELAY_SECONDS=3
RIFE_MOCK_SHOULD_FAIL=false
```

Use `RIFE_MOCK_SHOULD_FAIL=true` to test the failure path. Real BentoML is not required for this local flow.

`MINIO_PUBLIC_ENDPOINT=localhost:9000` controls the host used in browser download links. Keep it as `localhost:9000` for local Docker Compose unless you expose MinIO through another host name. `MINIO_REGION=us-east-1` lets the backend generate presigned URLs for the public endpoint without contacting that endpoint from inside the container.

## Docker Compose

Check the resolved configuration:

```bash
docker compose config
```

Build and start all services:

```bash
docker compose up -d --build
```

Inspect service state:

```bash
docker compose ps
```

Follow backend and worker logs while uploading a video:

```bash
docker compose logs -f backend worker
```

Useful service-specific logs:

```bash
docker compose logs backend
docker compose logs worker
docker compose logs redis-db
docker compose logs pg-db
docker compose logs minio-db
```

Stop the stack:

```bash
docker compose down
```

Stop and remove local volumes:

```bash
docker compose down -v
```

## Frontend Development

The production-like frontend container is available at `http://localhost:8080` after `docker compose up -d --build`.

For Vite development:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `http://localhost:8000` through `frontend/vite.config.js`.

Check the production build:

```bash
cd frontend
npm run build
```

## API Smoke Tests

Use a short valid MP4 sample under 10 MB and 15 seconds.

Upload with each valid coefficient:

```bash
curl -F "video=@sample.mp4" -F "coef=2" http://localhost:8000/api/videos
curl -F "video=@sample.mp4" -F "coef=3" http://localhost:8000/api/videos
curl -F "video=@sample.mp4" -F "coef=4" http://localhost:8000/api/videos
```

The optional `output_playback_mode` field controls the future RIFE/BentoML playback mode. It is queue-only for now and is not stored in PostgreSQL.

```bash
curl -F "video=@sample.mp4" -F "coef=2" -F "output_playback_mode=real_time" http://localhost:8000/api/videos
curl -F "video=@sample.mp4" -F "coef=2" -F "output_playback_mode=slow_motion" http://localhost:8000/api/videos
```

If the field is omitted, the backend defaults to `real_time`.

The response should include `video_id`, `validation_status`, `queue_status`, and `null` output/download fields before completion:

```json
{
  "video_id": 1,
  "staged_video_uri": "videos/input/<uuid>.mp4",
  "validation_status": "valid",
  "queue_status": "pending",
  "output_video_uri": null,
  "video_installing_uri": null
}
```

Poll until `queue_status` is `completed`:

```bash
curl http://localhost:8000/api/videos/<video_id>
```

After completion, `video_installing_uri` should be a browser-usable presigned MinIO URL using `localhost:9000` by default.

Invalid coefficients should be rejected:

```bash
curl -F "video=@sample.mp4" -F "coef=1" http://localhost:8000/api/videos
curl -F "video=@sample.mp4" -F "coef=5" http://localhost:8000/api/videos
```

Expected result: 4xx response with a message that coefficient must be `2`, `3`, or `4`.

Invalid playback modes should also be rejected:

```bash
curl -F "video=@sample.mp4" -F "coef=2" -F "output_playback_mode=bad" http://localhost:8000/api/videos
```

Expected result: 4xx response with a message that playback mode must be `real_time` or `slow_motion`.

## Browser Smoke Test

1. Open `http://localhost:8080` or the Vite dev URL.
2. Select or drag a valid short video.
3. Confirm the interpolation factor defaults to `x2`.
4. Confirm `Режим проигрывания` defaults to `обычный`.
5. Change the factor to `x2`, `x3`, or `x4`.
6. Change playback mode between `обычный` and `slow motion`.
7. Submit the video.
8. Watch the human-readable status progress from accepted to processing.
9. Wait for mock inference to complete.
10. Confirm a download link appears only after completion.
11. Confirm there is no raw `Server response` panel.

For the failure path:

1. Set `RIFE_MOCK_SHOULD_FAIL=true` in `.env`.
2. Recreate the worker container:

```bash
docker compose up -d --build worker
```

3. Upload a video again.
4. Confirm the frontend shows an error and does not show a download link.

## Database and Storage Checks

Inspect recent video rows:

```bash
docker compose exec pg-db psql -U interpolator -d video_interpolation -c \
"select video_id, queue_status, output_video_uri, coef from video_interpolation.input_videos order by video_id desc limit 5;"
```

MinIO console is available at `http://localhost:9001` with the credentials from `.env`. Input objects should appear under `input/`; completed mock outputs should appear under `output/` in the configured bucket.

Redis/RQ state is usually easiest to inspect through worker logs:

```bash
docker compose logs -f worker
```

## Metrics and Dashboards

Check backend metrics:

```bash
curl http://localhost:8000/metrics
```

Check Prometheus targets:

```bash
curl http://localhost:9090/api/v1/targets
```

The `backend` target should be `UP` after the stack is running. Grafana should have a provisioned Prometheus datasource pointing to `http://prometheus:9090`.

## Troubleshooting

- If a container is unhealthy, run `docker compose ps` and inspect that service's logs.
- If the backend is unavailable, check `docker compose logs backend` and confirm `BACKEND_PORT=8000`.
- If Vite cannot reach the API, confirm the backend is running on `localhost:8000` and `/api` is proxied in `frontend/vite.config.js`.
- If uploads are rejected, check file type, duration, size, and codec. Current limits are 10 MB and 15 seconds.
- If the worker marks jobs `failed`, inspect `docker compose logs worker`; with mock mode, check `RIFE_MOCK_SHOULD_FAIL`.
- If no download URL appears after completion, poll `GET /api/videos/<video_id>` and inspect `output_video_uri` in PostgreSQL.
- If Prometheus target is down, confirm the backend container is running and Prometheus uses target `backend:8000` inside the Compose network.
