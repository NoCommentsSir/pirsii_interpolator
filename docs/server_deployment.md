# Server Deployment Runbook

This guide is for running the production/server stack from source on a GPU server. Codex is not required on the server. The server user only runs the commands below.

## Required Layout

The two repositories must be siblings under the same parent directory:

```text
vfi_service/
  pirsii_interpolator/
  video_interpolation_arch/
```

All deployment commands in this guide are launched from:

```bash
cd /path/to/vfi_service/pirsii_interpolator
```

## Server Prerequisites

Run these checks first:

```bash
uname -a
lsb_release -a || cat /etc/os-release
git --version
docker --version
docker compose version
systemctl status docker
nvidia-smi
nvidia-smi -L
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

If the CUDA image tag is unavailable, choose another currently available `nvidia/cuda` base tag and rerun the same command. The important check is that `nvidia-smi` works inside a Docker container.

Docker must be configured with NVIDIA Container Toolkit. If `nvidia-smi` works on the host but `docker run --rm --gpus all ... nvidia-smi` fails, install or repair NVIDIA Container Toolkit using the official NVIDIA instructions for your Linux distribution, then restart Docker. Do not change application scripts to install GPU drivers or toolkit packages.

## DNS, Firewall, And HTTPS

Create two DNS records before starting Caddy:

```text
APP_DOMAIN   A record -> server public IP
FILES_DOMAIN A record -> server public IP
```

Open inbound ports:

```text
80/tcp
443/tcp
```

Caddy obtains HTTPS certificates automatically. After startup, expected Caddy logs should mention certificate acquisition or that certificates are already available.

Safe checks:

```bash
curl -I https://$APP_DOMAIN
curl -I https://$FILES_DOMAIN/minio/health/live
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs -f caddy
```

## Environment Setup

Create the server `.env`:

```bash
cp .env.server.example .env
nano .env
```

Change these values before the first start:

- `APP_DOMAIN`: public app host, for example `vfi.example.com`.
- `FILES_DOMAIN`: public MinIO file host, for example `vfi-files.example.com`.
- `REDIS_PASSWORD`: strong Redis password.
- `POSTGRES_PASSWORD`: strong PostgreSQL password.
- `MINIO_ROOT_PASSWORD`: strong MinIO password.
- `GF_SECURITY_ADMIN_PASSWORD`: strong Grafana admin password.

Keep these defaults unless your server layout intentionally differs:

- `REDIS_HOST=redis-db`
- `POSTGRES_HOST=pg-db`
- `MINIO_HOST=minio-db`
- `MINIO_PUBLIC_ENDPOINT=${FILES_DOMAIN}`
- `MINIO_PUBLIC_SECURE=true`
- `RIFE_API_PATH=/interpolate_video`
- `RIFE_REQUEST_TIMEOUT=1800`
- `RIFE_SHARED_DIR=/shared/rife`
- `RIFE_DEVICE=cuda`
- `RIFE_CODEC=h264_nvenc`
- `MODEL_WEIGHTS_ROOT=/app/model_weights`
- `MODEL_REPOS_ROOT=/app/model_repos`
- `DATASET_ROOT=/app/datasets`

If NVENC is unavailable but CUDA inference works, set:

```env
RIFE_CODEC=libx264
```

This keeps model inference on CUDA and uses CPU H.264 encoding.

## Preflight

Run the preflight helper from `pirsii_interpolator/`:

```bash
tools/server_preflight.sh
```

It prints diagnostics only. It checks the current directory, sibling repo paths, git status, Docker, Compose, NVIDIA tools, `.env`, model directories, ports `80/443`, and Compose config when the generated GPU compose file exists.

## GPU Compose Generation

List available GPUs:

```bash
nvidia-smi -L
```

Generate one worker+BentoML pair per GPU:

```bash
python3 tools/generate_gpu_compose.py --gpu-ids 0,1,2,3 --output docker-compose.gpu.generated.yml
```

For one GPU:

```bash
python3 tools/generate_gpu_compose.py --gpu-ids 0 --output docker-compose.gpu.generated.yml
```

Check the final Compose configuration:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml config
```

The generated file must not expose BentoML host ports. Each `rife-gpuN` service uses `expose: ["3000"]` and is reachable only inside the Compose network.

## Build And Run

Build and start the server stack:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml up -d --build
```

Check service status:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml ps
```

Follow important logs:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs -f backend
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs -f worker-gpu0
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs -f rife-gpu0
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs -f caddy
```

Stop the stack:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml down
```

Do not use `down -v` unless you intentionally want to delete PostgreSQL, Redis, MinIO, Grafana, and Caddy certificate volumes.

## Manual API Test

Use a short valid MP4 under the backend limits.

```bash
curl -F "video=@example_videos/001.mp4" -F "coef=2" https://$APP_DOMAIN/api/videos
```

If your sample is named differently:

```bash
curl -F "video=@example_videos/sample.mp4" -F "coef=2" https://$APP_DOMAIN/api/videos
```

The upload returns a `video_id`. Poll it:

```bash
curl https://$APP_DOMAIN/api/videos/<video_id>
```

Expected status sequence:

```text
pending -> processing -> completed
```

If the final status is `failed`, inspect:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs -f worker-gpu0
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs -f rife-gpu0
```

## Manual UI Test

Open:

```text
https://$APP_DOMAIN
```

Then:

1. Upload a short video.
2. Select interpolation factor `2`, `3`, or `4`.
3. Watch status updates.
4. Wait for `completed`.
5. Download the result.

The download URL should use `https://$FILES_DOMAIN/...`, not `localhost` and not `minio-db`.

## Prometheus And Grafana

Prometheus and Grafana are internal in server mode. The default server Compose does not publish their ports. To inspect them without changing Compose, use an SSH tunnel from your workstation:

```bash
ssh -L 9090:localhost:9090 -L 3000:localhost:3000 user@server
```

Then temporarily inspect from inside the Compose network or add explicit mappings only for a trusted maintenance window. Caddy is the only public ingress in the default server deployment.

## Troubleshooting

`docker compose config` fails:

- Confirm you are in `pirsii_interpolator/`.
- Confirm `.env` exists.
- Regenerate `docker-compose.gpu.generated.yml`.
- Check for accidental unsupported YAML edits.

Docker cannot access GPU:

- Run `nvidia-smi` on the host.
- Run `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`.
- Install or repair NVIDIA Container Toolkit.
- Restart Docker and rerun `tools/server_preflight.sh`.

`nvidia-smi` works on host but not in container:

- Docker is not configured for NVIDIA runtime.
- Check NVIDIA Container Toolkit installation.
- Check that the Docker daemon was restarted after toolkit setup.

Caddy cannot get a certificate:

- Confirm `APP_DOMAIN` and `FILES_DOMAIN` DNS records resolve to this server.
- Confirm ports `80` and `443` are open inbound.
- Confirm no other service is using host ports `80` or `443`.
- Inspect `docker compose ... logs -f caddy`.

DNS does not resolve to the server IP:

```bash
dig $APP_DOMAIN
dig $FILES_DOMAIN
```

Fix DNS before restarting Caddy.

Files domain download URL points to localhost:

- Check `.env`.
- `MINIO_PUBLIC_ENDPOINT` must be `${FILES_DOMAIN}` or the actual public files domain.
- `MINIO_PUBLIC_SECURE=true` must be set for HTTPS links.
- Restart backend after changing `.env`.

MinIO presigned URL returns `403`:

- Confirm `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` are unchanged between backend and MinIO.
- Confirm server time is correct.
- Confirm the object exists in the configured bucket.
- Confirm the presigned URL host is `FILES_DOMAIN`.

Worker says BentoML connection refused:

- Inspect `docker compose ... ps`.
- Check `rife-gpuN` logs.
- Confirm `worker-gpuN` uses `RIFE_SERVICE_URL=http://rife-gpuN:3000`.
- Confirm both services are in the same Compose project.

Worker cannot find `output_path`:

- Confirm both `worker-gpuN` and `rife-gpuN` mount the same named volume.
- Confirm worker paths are under `/shared/rife`.
- Temporarily set `RIFE_KEEP_JOB_DIR=true`, restart the worker, and inspect the job directory.

Model weights missing:

- Check sibling path `../video_interpolation_arch/model_weights`.
- Check `../video_interpolation_arch/model_repos`.
- Check `../video_interpolation_arch/configs`.
- Inspect `rife-gpuN` logs for the exact missing file path.

Host ports `80/443` already occupied:

```bash
sudo ss -ltnp | grep -E ':80|:443'
```

Stop or reconfigure the conflicting service before starting Caddy.

Server has no Node/npm:

- This is expected.
- Frontend is built inside Docker from `frontend/Dockerfile` using the Node build stage.
- Do not install Node/npm on the host just for deployment.

Build context is huge:

- Confirm `video_interpolation_arch/.dockerignore` exists.
- Confirm `pirsii_interpolator/.dockerignore` and `frontend/.dockerignore` exist.
- Confirm `model_weights`, `datasets`, `raw_data`, `outputs`, `node_modules`, and `dist` are not sent as Docker build context.
