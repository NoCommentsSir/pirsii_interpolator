# Grafana Dashboard

This project provisions Grafana from files. Do not create or edit the main dashboard manually in the Grafana UI unless you plan to export the JSON and commit the change.

## Provisioned Files

- `grafana/provisioning/datasources/datasources.yml` defines datasources:
  - `Prometheus`, UID `prometheus`, URL `http://prometheus:9090`
  - `Pirsii PostgreSQL`, UID `pirsii-postgres`, URL `pg-db:5432`
- `grafana/provisioning/dashboards/dashboards.yml` tells Grafana to load dashboards from `/etc/grafana/dashboards`.
- `grafana/dashboards/pirsii-vfi-service-overview.json` is the provisioned dashboard.

The main dashboard is `Pirsii VFI Service Overview` with UID `pirsii-vfi-overview`.

## Start Local Observability

From `pirsii_interpolator/`:

```bash
cp .env.example .env
docker compose config
docker compose up -d --build pg-db redis-db minio-db backend prometheus grafana
docker compose ps
```

Local Compose exposes Grafana and Prometheus for debugging:

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Backend metrics: `http://localhost:8000/metrics`

Use the Grafana credentials from `.env`:

```bash
set -a
source .env
set +a

curl -u "$GF_SECURITY_ADMIN_USER:$GF_SECURITY_ADMIN_PASSWORD" \
  http://localhost:3000/api/datasources

curl -u "$GF_SECURITY_ADMIN_USER:$GF_SECURITY_ADMIN_PASSWORD" \
  "http://localhost:3000/api/search?query=Pirsii"
```

## Start Server Observability

Server mode keeps Grafana and Prometheus internal. Start the server stack with the server Compose file and the generated GPU overlay:

```bash
python3 tools/generate_gpu_compose.py --gpu-ids 0 --output docker-compose.gpu.generated.yml
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml config
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml up -d --build
```

Check provisioning logs:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs grafana
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs prometheus
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml logs dcgm-exporter
```

Check APIs from inside the Compose network:

```bash
docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml exec prometheus \
  wget -qO- http://backend:8000/metrics

docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml exec prometheus \
  wget -qO- http://localhost:9090/api/v1/targets

docker compose -f docker-compose.server.yml -f docker-compose.gpu.generated.yml exec prometheus \
  wget -qO- http://grafana:3000/api/health
```

Do not publish Prometheus or Grafana directly to the internet. If you need browser access on a server, bind a temporary override to `127.0.0.1` only and access it through SSH port forwarding.

Example temporary override:

```yaml
services:
  grafana:
    ports:
      - "127.0.0.1:3000:3000"
  prometheus:
    ports:
      - "127.0.0.1:9090:9090"
```

Then run Compose with that extra file and forward ports from your workstation:

```bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 root@SERVER_PUBLIC_IP
```

## Prometheus Targets

Local Prometheus uses `prometheus/prometheus.yml` and scrapes:

- `prometheus`
- `backend`

Server Prometheus uses `prometheus/prometheus.server.yml` and scrapes:

- `prometheus`
- `backend`
- `dcgm-exporter`

The dashboard GPU panels use DCGM metrics such as `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_GPU_TEMP`, `DCGM_FI_DEV_POWER_USAGE`, and `DCGM_FI_DEV_XID_ERRORS`.

If the server has no NVIDIA Container Toolkit or DCGM exporter is not running, GPU panels will show no data. That does not break the rest of the dashboard.

## Empty Panels

PostgreSQL job panels read from `video_interpolation.input_videos`.

Quality panels read from `video_interpolation.online_metrics`. Empty quality panels usually mean the worker has not written online metrics yet, or the current dashboard time range does not include those rows.

Prometheus API panels depend on the backend `/metrics` endpoint exposed by `prometheus-fastapi-instrumentator`. If those panels are empty, check:

```bash
curl http://localhost:8000/metrics
curl http://localhost:9090/api/v1/targets
```

On the server, run the same checks inside the relevant containers as shown above.

## PostgreSQL Credentials

The Grafana PostgreSQL datasource uses existing Compose environment variables:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

This is acceptable for the MVP but is technical debt. A production deployment should use a read-only database user. The repository currently has no migration mechanism, and existing server volumes would still require manual SQL.

Manual read-only user example:

```sql
CREATE USER grafana_reader WITH PASSWORD 'replace-with-a-strong-password';
GRANT CONNECT ON DATABASE video_interpolation TO grafana_reader;
GRANT USAGE ON SCHEMA video_interpolation TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA video_interpolation TO grafana_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA video_interpolation
  GRANT SELECT ON TABLES TO grafana_reader;
```

After adding a read-only user, update the Grafana datasource provisioning to use reader-specific environment variables and restart Grafana.

## Data Safety

The dashboard must not display presigned MinIO URLs or internal object paths. The recent jobs table shows only IDs, status, input profile, latency, and whether an output exists.
