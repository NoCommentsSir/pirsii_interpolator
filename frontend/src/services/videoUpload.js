const API_URL = "/api/videos";
const DEFAULT_POLL_INTERVAL_MS = 3000;

function delay(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function uploadVideoFile(file) {
    const formData = new FormData();
    formData.append("video", file);
    formData.append("coef", "2");

    const response = await fetch(API_URL, {
        method: "POST",
        body: formData,
    });

    const text = await response.text();
    let payload;
    try {
        payload = JSON.parse(text);
    } catch {
        payload = text;
    }

    if (!response.ok) {
        throw new Error(String(payload) || response.statusText);
    }

    return payload;
}

/**
 * insertVideo - POSTs a video file to the backend `/api/videos` endpoint
 * and returns the parsed JSON response (VideoResponse) or throws an Error
 * with the backend `detail` if present.
 */
export async function insertVideo(file) {
    const formData = new FormData();
    formData.append("video", file);
    formData.append("coef", "1");

    const response = await fetch(API_URL, { method: "POST", body: formData });

    // Try to parse JSON body when available
    const contentType = response.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");

    let payload = null;
    if (isJson) {
        try {
            payload = await response.json();
        } catch (e) {
            // ignore parse errors
            payload = null;
        }
    } else {
        payload = await response.text();
    }

    if (!response.ok) {
        throw new Error(String(payload) || response.statusText);
    }

    return payload;
}

export async function pollVideoJob({
    jobId,
    statusUrl,
    maxAttempts = 40,
    intervalMs = DEFAULT_POLL_INTERVAL_MS,
}) {
    const endpoint = statusUrl || `${API_URL}/${jobId}`;

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        const response = await fetch(endpoint, {
            method: "GET",
        });

        if (!response.ok) {
            throw new Error(
                response.statusText || "Не удалось получить статус обработки",
            );
        }

        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json")
            ? await response.json()
            : { status: await response.text() };

        const status = String(
            payload.status || payload.state || "",
        ).toLowerCase();

        if (status === "done" || status === "ready" || status === "completed") {
            return payload;
        }

        if (status === "error" || status === "failed") {
            throw new Error(
                payload.message || payload.error || "Ошибка обработки видео",
            );
        }

        await delay(intervalMs);
    }

    throw new Error(
        "Видео все еще обрабатывается. Попробуйте обновить страницу чуть позже.",
    );
}
