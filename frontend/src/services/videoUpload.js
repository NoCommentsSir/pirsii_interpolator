const API_URL = "/api/videos";
const DEFAULT_POLL_INTERVAL_MS = 3000;

function delay(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function parseResponse(response) {
    const text = await response.text();
    if (!text) {
        return null;
    }

    try {
        return JSON.parse(text);
    } catch {
        return text;
    }
}

function errorMessageFromPayload(payload, fallback) {
    if (!payload) {
        return fallback;
    }

    if (typeof payload === "string") {
        return payload;
    }

    if (typeof payload.detail === "string") {
        return payload.detail;
    }

    if (Array.isArray(payload.detail)) {
        return payload.detail
            .map((item) => item?.msg || JSON.stringify(item))
            .join("; ");
    }

    return fallback;
}

export async function uploadVideoFile(
    file,
    coef = 2,
    outputPlaybackMode = "real_time",
) {
    const formData = new FormData();
    formData.append("video", file);
    formData.append("coef", String(coef));
    formData.append("output_playback_mode", outputPlaybackMode);

    const response = await fetch(API_URL, {
        method: "POST",
        body: formData,
    });

    const payload = await parseResponse(response);

    if (!response.ok) {
        throw new Error(errorMessageFromPayload(payload, response.statusText));
    }

    return payload;
}

export async function pollVideoJob({
    videoId,
    maxAttempts = 80,
    intervalMs = DEFAULT_POLL_INTERVAL_MS,
    onStatus,
}) {
    const endpoint = `${API_URL}/${videoId}`;

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        const response = await fetch(endpoint, {
            method: "GET",
        });

        const payload = await parseResponse(response);

        if (!response.ok) {
            throw new Error(
                errorMessageFromPayload(
                    payload,
                    "Не удалось получить статус обработки",
                ),
            );
        }

        const status = String(payload?.queue_status || "").toLowerCase();
        onStatus?.(payload);

        if (status === "completed") {
            if (!payload.video_installing_uri) {
                throw new Error(
                    "Видео обработано, но ссылка на скачивание не пришла.",
                );
            }
            return payload;
        }

        if (status === "failed") {
            throw new Error(
                payload.message || payload.error || "Ошибка обработки видео",
            );
        }

        if (status !== "pending" && status !== "processing") {
            throw new Error(`Неизвестный статус обработки: ${status || "-"}`);
        }

        await delay(intervalMs);
    }

    throw new Error(
        "Видео все еще обрабатывается. Попробуйте обновить страницу чуть позже.",
    );
}
