const API_URL = "/api/videos";
const DEFAULT_POLL_INTERVAL_MS = 3000;

function delay(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function uploadVideoFile(file) {
    const formData = new FormData();
    formData.append("video", file);

    const response = await fetch(API_URL, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Не удалось отправить видео");
    }

    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
        return response.json();
    }

    return response.text();
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
            const errorText = await response.text();
            throw new Error(
                errorText || "Не удалось получить статус обработки",
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
