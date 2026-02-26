"use client";

import { useCallback, useState, useEffect } from "react";
import { Upload, CheckCircle, XCircle, Loader2, Archive } from "lucide-react";

interface Document {
    id: number;
    filename: string;
    original_filename: string;
    status: "processing" | "ready" | "failed";
    processing_stage?: string;
    processing_progress?: number;
    error_message?: string;
    page_count?: number;
    created_at: string;
}

interface UploadZoneProps {
    onDocumentUploaded: (doc: Document) => void;
    onDocumentReady: (docId: number, pageCount: number) => void;
}

const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".txt"];
const ARCHIVE_EXTENSIONS = [".zip", ".rar"];
const ALL_EXTENSIONS = [...SUPPORTED_EXTENSIONS, ...ARCHIVE_EXTENSIONS];
const ACCEPT_STRING = ".pdf,.docx,.xlsx,.txt,.zip,.rar,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,application/zip,application/x-rar-compressed";

const stageLabels: Record<string, string> = {
    uploading: "Загрузка файла...",
    checking_ollama: "Проверка AI сервиса...",
    extracting_text: "Извлечение текста...",
    chunking: "Разбиение на чанки...",
    generating_embeddings: "Генерация эмбеддингов...",
    storing_vectors: "Сохранение векторов...",
    completed: "Готово!",
    failed: "Ошибка обработки"
};

function isSupported(filename: string): boolean {
    const ext = filename.toLowerCase().split(".").pop();
    return ext ? ALL_EXTENSIONS.includes(`.${ext}`) : false;
}

function isArchive(filename: string): boolean {
    const ext = filename.toLowerCase().split(".").pop();
    return ext ? ARCHIVE_EXTENSIONS.includes(`.${ext}`) : false;
}

export default function UploadZone({
    onDocumentUploaded,
    onDocumentReady,
}: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<{
        type: "success" | "error" | null;
        message: string;
    }>({ type: null, message: "" });
    const [processingDocs, setProcessingDocs] = useState<number[]>([]);
    const [processingInfo, setProcessingInfo] = useState<Record<number, { stage: string; progress: number }>>({});

    useEffect(() => {
        if (processingDocs.length === 0) return;

        const interval = setInterval(async () => {
            for (const docId of processingDocs) {
                try {
                    const response = await fetch(`/api/documents/${docId}`);
                    if (response.ok) {
                        const doc = await response.json();

                        if (doc.status === "processing") {
                            setProcessingInfo(prev => ({
                                ...prev,
                                [docId]: {
                                    stage: doc.processing_stage || "uploading",
                                    progress: doc.processing_progress || 0
                                }
                            }));
                        }

                        if (doc.status === "ready") {
                            onDocumentReady(docId, doc.page_count || 0);
                            setProcessingDocs((prev) => prev.filter((id) => id !== docId));
                            setProcessingInfo(prev => {
                                const next = { ...prev };
                                delete next[docId];
                                return next;
                            });
                            setUploadStatus({
                                type: "success",
                                message: `Документ обработан`,
                            });
                        } else if (doc.status === "failed") {
                            setProcessingDocs((prev) => prev.filter((id) => id !== docId));
                            setProcessingInfo(prev => {
                                const next = { ...prev };
                                delete next[docId];
                                return next;
                            });
                            setUploadStatus({
                                type: "error",
                                message: doc.error_message
                                    ? `Ошибка: ${doc.error_message.slice(0, 50)}...`
                                    : "Ошибка обработки",
                            });
                        }
                    }
                } catch (error) {
                    console.error("Error polling document status:", error);
                }
            }
        }, 2000);

        return () => clearInterval(interval);
    }, [processingDocs, onDocumentReady]);

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    }, []);

    const handleDragIn = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    }, []);

    const handleDragOut = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFiles(files);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            handleFiles(files);
        }
    };

    const handleFiles = async (files: FileList) => {
        const validFiles: File[] = [];
        for (let i = 0; i < files.length; i++) {
            if (isSupported(files[i].name)) {
                validFiles.push(files[i]);
            }
        }

        if (validFiles.length === 0) {
            setUploadStatus({
                type: "error",
                message: "Только PDF, Word, Excel, TXT, ZIP, RAR"
            });
            return;
        }

        setIsUploading(true);
        setUploadStatus({ type: null, message: "" });

        try {
            if (validFiles.length === 1 && !isArchive(validFiles[0].name)) {
                const formData = new FormData();
                formData.append("file", validFiles[0]);

                const response = await fetch("/api/upload", {
                    method: "POST",
                    body: formData,
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || "Upload failed");
                }

                const data = await response.json();

                onDocumentUploaded({
                    id: data.document_id,
                    filename: validFiles[0].name,
                    original_filename: validFiles[0].name,
                    status: "processing",
                    created_at: new Date().toISOString(),
                });

                setProcessingDocs((prev) => [...prev, data.document_id]);
                setProcessingInfo(prev => ({
                    ...prev,
                    [data.document_id]: { stage: "uploading", progress: 0 }
                }));
            } else {
                const formData = new FormData();
                for (const file of validFiles) {
                    formData.append("files", file);
                }

                const response = await fetch("/api/upload/batch", {
                    method: "POST",
                    body: formData,
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || "Batch upload failed");
                }

                const data = await response.json();
                let successCount = 0;

                for (const result of data.results) {
                    if (result.status === "processing") {
                        successCount++;
                        onDocumentUploaded({
                            id: result.document_id,
                            filename: result.filename,
                            original_filename: result.filename,
                            status: "processing",
                            created_at: new Date().toISOString(),
                        });

                        setProcessingDocs((prev) => [...prev, result.document_id]);
                        setProcessingInfo(prev => ({
                            ...prev,
                            [result.document_id]: { stage: "uploading", progress: 0 }
                        }));
                    }
                }

                if (successCount === 0) {
                    setUploadStatus({ type: "error", message: "Не удалось загрузить файлы" });
                }
            }
        } catch (error) {
            setUploadStatus({
                type: "error",
                message: error instanceof Error ? error.message : "Ошибка загрузки",
            });
        } finally {
            setIsUploading(false);
        }
    };

    const activeProcessing = processingDocs.map(docId => processingInfo[docId]).filter(Boolean);
    const currentStage = activeProcessing.length > 0 ? activeProcessing[0] : null;

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div
                onDragEnter={handleDragIn}
                onDragLeave={handleDragOut}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`upload-area ${isDragging ? "drag-over" : ""}`}
                style={{ margin: 0, position: "relative" }}
            >
                <input
                    type="file"
                    accept={ACCEPT_STRING}
                    onChange={handleFileInput}
                    style={{ position: "absolute", inset: 0, opacity: 0, cursor: "pointer", zIndex: 10 }}
                    disabled={isUploading}
                    multiple
                />

                {isUploading ? (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                        <Loader2 style={{ width: 24, height: 24, color: "var(--accent)", animation: "spin 1s linear infinite" }} />
                        <h3 style={{ fontSize: 12 }}>Обработка...</h3>
                    </div>
                ) : (
                    <>
                        <div className="upload-area-icon">
                            <Upload style={{ width: 16, height: 16, color: "var(--accent)" }} />
                        </div>
                        <h3>Перетащите файлы сюда</h3>
                        <p>PDF, DOCX, TXT, ZIP, RAR</p>
                    </>
                )}
            </div>

            {uploadStatus.type && (
                <div style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "8px 10px", borderRadius: 8, fontSize: 11,
                    background: uploadStatus.type === "success" ? "var(--green-dim)" : "var(--red-dim)",
                    color: uploadStatus.type === "success" ? "var(--green)" : "var(--red)"
                }}>
                    {uploadStatus.type === "success" ? <CheckCircle style={{ width: 12, height: 12 }} /> : <XCircle style={{ width: 12, height: 12 }} />}
                    <span>{uploadStatus.message}</span>
                </div>
            )}

            {processingDocs.length > 0 && currentStage && (
                <div style={{
                    padding: "8px 10px", borderRadius: 8, fontSize: 11,
                    background: "rgba(251,191,36,0.1)", color: "var(--amber)"
                }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <span style={{ fontWeight: 500 }}>
                            {processingDocs.length > 1 ? `Обработка ${processingDocs.length} файлов...` : stageLabels[currentStage.stage] || "В работе..."}
                        </span>
                        <span>{currentStage.progress}%</span>
                    </div>
                    <div style={{ height: 4, background: "rgba(255,255,255,0.1)", borderRadius: 10, overflow: "hidden" }}>
                        <div style={{
                            width: `${currentStage.progress}%`,
                            height: "100%", background: "var(--amber)",
                            transition: "width 0.3s ease"
                        }} />
                    </div>
                </div>
            )}
        </div>
    );
}
