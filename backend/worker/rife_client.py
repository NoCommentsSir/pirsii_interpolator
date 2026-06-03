import os
import logging
import json
import requests

logger = logging.getLogger(__name__)

RIFE_SERVICE_URL = os.getenv("RIFE_SERVICE_URL", "http://localhost:5173")
RIFE_API_PATH = os.getenv("RIFE_API_PATH", "/interpolate_video")
RIFE_REQUEST_TIMEOUT = int(os.getenv("RIFE_REQUEST_TIMEOUT", "600"))


def call_rife_inference(input_path: str, output_path: str, coef: int) -> None:
    if not RIFE_SERVICE_URL:
        raise RuntimeError("RIFE_SERVICE_URL is not configured")

    url = f"{RIFE_SERVICE_URL.rstrip('/')}{RIFE_API_PATH}"
    logger.info("Calling RIFE BentoML API %s", url)

    params = {
        "input_path": input_path,
        "output_path": output_path,
        "interpolation_factor": coef
    }
    logger.info(f"Calling RIFE BentoML API with parameters: {params}")
    response = requests.post(url, data=json.dumps(params), timeout=RIFE_REQUEST_TIMEOUT)

    if response.status_code != 200:
        raise RuntimeError(
            "RIFE API request failed: %s %s" % (response.status_code, response.text)
        )

    logger.info("RIFE BentoML API returned %d bytes", len(response.content))
