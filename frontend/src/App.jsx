import { useEffect, useRef, useState } from "react";
import { pollVideoJob, uploadVideoFile } from "./services/videoUpload.js";

const UPLOAD_LIMITS = {
    maxDurationSeconds: 15,
    maxSizeBytes: 30 * 1024 * 1024,
    maxLongSide: 1920,
    maxShortSide: 1080,
};

function App() {
    const inputRef = useRef(null);
    const [selectedFile, setSelectedFile] = useState(null);
    const [dragActive, setDragActive] = useState(false);
    const [validationMessage, setValidationMessage] = useState("");
    const [statusMessage, setStatusMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [downloadUrl, setDownloadUrl] = useState("");

    useEffect(() => {
        return () => {
            if (selectedFile?.previewUrl) {
                URL.revokeObjectURL(selectedFile.previewUrl);
            }
        };
    }, [selectedFile]);

    const formatFileSize = (bytes) => {
        const megabytes = bytes / (1024 * 1024);
        return `${megabytes.toFixed(megabytes >= 10 ? 0 : 1)} MB`;
    };

    const readVideoMetadata = (file) => {
        return new Promise((resolve, reject) => {
            const video = document.createElement("video");
            const objectUrl = URL.createObjectURL(file);

            video.preload = "metadata";
            video.src = objectUrl;

            video.onloadedmetadata = () => {
                URL.revokeObjectURL(objectUrl);
                resolve({
                    duration: video.duration,
                    width: video.videoWidth,
                    height: video.videoHeight,
                });
            };

            video.onerror = () => {
                URL.revokeObjectURL(objectUrl);
                reject(new Error("Не удалось прочитать видео"));
            };
        });
    };

    const validateFile = async (file) => {
        if (!file) {
            return;
        }

        setSelectedFile(null);
        setValidationMessage("");
        setStatusMessage("");
        setDownloadUrl("");

        if (!file.type.startsWith("video/")) {
            setValidationMessage("Нужно загрузить видеофайл.");
            return;
        }

        if (file.size > UPLOAD_LIMITS.maxSizeBytes) {
            setValidationMessage(
                `Видео должно быть не больше ${UPLOAD_LIMITS.maxSizeBytes / (1024 * 1024)} МБ.`,
            );
            return;
        }

        try {
            const { duration, width, height } = await readVideoMetadata(file);
            const longSide = Math.max(width, height);
            const shortSide = Math.min(width, height);

            if (duration > UPLOAD_LIMITS.maxDurationSeconds) {
                setValidationMessage(
                    `Видео должно быть не длиннее ${UPLOAD_LIMITS.maxDurationSeconds} секунд.`,
                );
                return;
            }

            if (
                longSide > UPLOAD_LIMITS.maxLongSide ||
                shortSide > UPLOAD_LIMITS.maxShortSide
            ) {
                setValidationMessage(
                    `Разрешение должно быть не больше ${UPLOAD_LIMITS.maxLongSide}x${UPLOAD_LIMITS.maxShortSide}.`,
                );
                return;
            }

            setSelectedFile({
                file,
                duration,
                width,
                height,
                previewUrl: URL.createObjectURL(file),
            });
            setStatusMessage("Видео прошло проверку и готово к отправке.");
        } catch {
            setValidationMessage(
                "Не удалось проверить видео. Попробуйте другой файл.",
            );
        }
    };

    const handleInputChange = async (event) => {
        const file = event.target.files?.[0];
        await validateFile(file);
        event.target.value = "";
    };

    const handleDrop = async (event) => {
        event.preventDefault();
        setDragActive(false);

        const file = event.dataTransfer.files?.[0];
        await validateFile(file);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        if (!selectedFile) {
            setValidationMessage("Сначала загрузите подходящее видео.");
            return;
        }

        setIsSubmitting(true);
        setValidationMessage("");
        setDownloadUrl("");

        try {
            const uploadResult = await uploadVideoFile(selectedFile.file);
            const jobId = uploadResult?.jobId || uploadResult?.id;
            const statusUrl = uploadResult?.statusUrl;
            const initialDownloadUrl = uploadResult?.downloadUrl;

            if (initialDownloadUrl) {
                setDownloadUrl(initialDownloadUrl);
                setStatusMessage(`Файл ${selectedFile.file.name} уже готов.`);
                return;
            }

            if (!jobId && !statusUrl) {
                throw new Error(
                    "Сервер не вернул идентификатор задачи для polling.",
                );
            }

            setStatusMessage(
                "Видео принято. Обработка занимает 1-2 минуты или дольше.",
            );

            const jobResult = await pollVideoJob({
                jobId,
                statusUrl,
            });

            const finalDownloadUrl = jobResult?.downloadUrl || jobResult?.url;

            if (!finalDownloadUrl) {
                throw new Error(
                    "Видео обработано, но ссылка на скачивание не пришла.",
                );
            }

            setDownloadUrl(finalDownloadUrl);
            setStatusMessage("Видео обработано. Можно скачать готовый файл.");
        } catch (error) {
            setValidationMessage(
                error instanceof Error
                    ? error.message
                    : "Не удалось отправить видео.",
            );
        } finally {
            setIsSubmitting(false);
        }
    };

    const openFilePicker = () => {
        inputRef.current?.click();
    };

    const highlights = [
        {
            value: `${UPLOAD_LIMITS.maxDurationSeconds} сек`,
            label: "длительность",
        },
        {
            value: `${UPLOAD_LIMITS.maxSizeBytes / (1024 * 1024)} МБ`,
            label: "размер",
        },
        {
            value: `${UPLOAD_LIMITS.maxLongSide}x${UPLOAD_LIMITS.maxShortSide}`,
            label: "разрешение",
        },
    ];

    return (
        <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-4 py-8 sm:px-6 lg:px-8">
            <section className="flex w-full flex-col gap-6">
                <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 sm:p-8 lg:p-10">
                    <p className="mb-3 text-sm font-medium uppercase tracking-[0.18em] text-slate-400">
                        ПИРСИИнтерполятор
                    </p>
                    <h1 className="text-2xl font-semibold text-white sm:text-3xl">
                        Интерполяция кадров в видео в 2 раза быстрее
                    </h1>
                    <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300 sm:text-base">
                        Загружайте короткое видео до{" "}
                        {UPLOAD_LIMITS.maxDurationSeconds} секунд и{" "}
                        {UPLOAD_LIMITS.maxSizeBytes / (1024 * 1024)} МБ.
                    </p>

                    <div className="mt-6 grid gap-3 sm:grid-cols-3">
                        {highlights.map((item) => (
                            <div
                                key={item.label}
                                className="rounded-xl border border-slate-800 bg-slate-950 p-4"
                            >
                                <span className="block text-xl font-semibold text-white">
                                    {item.value}
                                </span>
                                <span className="mt-1 block text-sm text-slate-400">
                                    {item.label}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                <form
                    className="rounded-2xl border border-slate-800 bg-slate-900 p-4 sm:p-6 lg:p-8"
                    onSubmit={handleSubmit}
                >
                    <input
                        ref={inputRef}
                        className="sr-only"
                        type="file"
                        accept="video/*"
                        onChange={handleInputChange}
                    />

                    <div
                        className={`flex min-h-[320px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-6 py-8 text-center transition sm:px-10 ${
                            dragActive
                                ? "border-slate-500 bg-slate-950"
                                : "border-slate-700 bg-slate-950"
                        }`}
                        onClick={openFilePicker}
                        onDragEnter={() => setDragActive(true)}
                        onDragOver={(event) => {
                            event.preventDefault();
                            setDragActive(true);
                        }}
                        onDragLeave={() => setDragActive(false)}
                        onDrop={handleDrop}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                openFilePicker();
                            }
                        }}
                    >
                        <div className="flex h-14 w-14 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-2xl text-slate-300">
                            ⇪
                        </div>
                        <h2 className="mt-5 text-xl font-semibold text-white sm:text-2xl">
                            Перетащите видео сюда
                        </h2>
                        <p className="mt-3 max-w-md text-sm leading-6 text-slate-400 sm:text-base">
                            Или нажмите кнопку, чтобы выбрать файл вручную.
                        </p>

                        <button
                            type="button"
                            className="mt-6 inline-flex items-center justify-center rounded-full border border-slate-700 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800"
                            onClick={(event) => {
                                event.stopPropagation();
                                openFilePicker();
                            }}
                        >
                            Загрузить видео
                        </button>
                    </div>

                    <div className="mt-4 flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-950 p-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                                Текущий файл
                            </p>
                            <strong className="mt-1 block text-base font-semibold text-white">
                                {selectedFile
                                    ? selectedFile.file.name
                                    : "Файл не выбран"}
                            </strong>
                            <span className="mt-1 block text-sm text-slate-400">
                                {selectedFile
                                    ? `${formatFileSize(selectedFile.file.size)} · ${selectedFile.duration.toFixed(1)} сек · ${selectedFile.width}x${selectedFile.height}`
                                    : "Поддерживаются только видеофайлы"}
                            </span>
                        </div>

                        <button
                            type="submit"
                            className="inline-flex items-center justify-center rounded-full bg-slate-100 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!selectedFile || isSubmitting}
                        >
                            {isSubmitting ? "Отправка..." : "Отправить"}
                        </button>
                    </div>

                    {validationMessage ? (
                        <p className="mt-4 rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-200">
                            {validationMessage}
                        </p>
                    ) : null}

                    {statusMessage ? (
                        <p className="mt-4 rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-300">
                            {statusMessage}
                        </p>
                    ) : null}

                    {downloadUrl ? (
                        <a
                            href={downloadUrl}
                            className="mt-4 inline-flex items-center justify-center rounded-full border border-slate-700 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800"
                            download
                        >
                            Скачать готовое видео
                        </a>
                    ) : null}

                    {selectedFile ? (
                        <div className="mt-4 overflow-hidden rounded-xl border border-slate-800 bg-slate-950 p-3">
                            <video
                                className="block w-full rounded-lg bg-black"
                                src={selectedFile.previewUrl}
                                controls
                            />
                        </div>
                    ) : null}
                </form>
            </section>
        </main>
    );
}

export default App;
