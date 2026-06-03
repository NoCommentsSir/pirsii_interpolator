import os
import logging
import shutil
import time
import requests
import json

logger = logging.getLogger(__name__)

RIFE_SERVICE_URL = os.getenv("RIFE_SERVICE_URL", "mock://local")
RIFE_API_PATH = os.getenv("RIFE_API_PATH", "/interpolate_video")
RIFE_REQUEST_TIMEOUT = int(os.getenv("RIFE_REQUEST_TIMEOUT", "600"))
RIFE_MOCK_DELAY_SECONDS = float(os.getenv("RIFE_MOCK_DELAY_SECONDS", "3"))


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _run_mock_inference(input_path: str, output_path: str, output_playback_mode: str) -> None:
    logger.info(
        "Running local mock RIFE inference with delay %.1f seconds and playback mode %s",
        RIFE_MOCK_DELAY_SECONDS,
        output_playback_mode,
    )

    if _env_flag("RIFE_MOCK_SHOULD_FAIL"):
        time.sleep(RIFE_MOCK_DELAY_SECONDS)
        raise RuntimeError("Mock RIFE inference was configured to fail")

    time.sleep(RIFE_MOCK_DELAY_SECONDS)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    shutil.copyfile(input_path, output_path)

    if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
        raise RuntimeError("Mock RIFE inference did not create a valid output file")


def call_rife_inference(
    input_path: str,
    output_path: str,
    coef: int,
    output_playback_mode: str = "real_time",
) -> None:
    if not RIFE_SERVICE_URL:
        raise RuntimeError("RIFE_SERVICE_URL is not configured")

    if RIFE_SERVICE_URL.startswith("mock://"):
        _run_mock_inference(input_path, output_path, output_playback_mode)
        return

    url = f"{RIFE_SERVICE_URL.rstrip('/')}{RIFE_API_PATH}"
    logger.info("Calling RIFE BentoML API %s", url)

    params = {
        "input_path": input_path,
        "output_path": output_path,
        "interpolation_factor": coef,
        "output_playback_mode": output_playback_mode,
    }
    logger.info(f"Calling RIFE BentoML API with parameters: {params}")
    response = requests.post(url, json=params, timeout=RIFE_REQUEST_TIMEOUT)

    if response.status_code != 200:
        raise RuntimeError(
            "RIFE API request failed: %s %s" % (response.status_code, response.text)
        )

    logger.info("RIFE BentoML API returned %d bytes", len(response.content))
    return json.loads(response.content)
