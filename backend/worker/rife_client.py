import os
import logging

import requests

logger = logging.getLogger(__name__)

RIFE_SERVICE_URL = os.getenv("RIFE_SERVICE_URL", "")
RIFE_API_PATH = os.getenv("RIFE_API_PATH", "/predict")
RIFE_REQUEST_TIMEOUT = int(os.getenv("RIFE_REQUEST_TIMEOUT", "600"))


def call_rife_inference(input_path: str, output_path: str, coef: int) -> None:
    """Call external BentoML RIFE inference service.

    This is NOT a local model call. The service is a separate API.
    It should accept multipart/form-data with the video file and interpolation factor.
    """
    if not RIFE_SERVICE_URL:
        raise RuntimeError("RIFE_SERVICE_URL is not configured")

    url = f"{RIFE_SERVICE_URL.rstrip('/')}{RIFE_API_PATH}"
    logger.info("Calling RIFE BentoML API %s", url)

    with open(input_path, "rb") as input_file:
        files = {"video": (os.path.basename(input_path), input_file, "video/mp4")}
        data = {"coef": str(coef)}

        response = requests.post(url, files=files, data=data, timeout=RIFE_REQUEST_TIMEOUT)

    if response.status_code != 200:
        raise RuntimeError(
            "RIFE API request failed: %s %s" % (response.status_code, response.text)
        )

    with open(output_path, "wb") as output_file:
        output_file.write(response.content)

    logger.info("RIFE BentoML API returned %d bytes", len(response.content))
