"use client";

import { useCallback, useState, useEffect } from "react";
import { Upload, CheckCircle, XCircle, Loader2 } from "lucide-react";

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
const ACCEPT_STRING = ".pdf,.docx,.xlsx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain";

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
    return ext ? SUPPORTED_EXTENSIONS.includes(`.${ext}`) : false;
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

                        // Update processing info for real-time progress
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
                                message: `Документ обработан: ${doc.chunk_count || '?'} чанков`,
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
                                    ? `Ошибка: ${doc.error_message.slice(0, 200)}`
                                    : "Ошибка обработки документа",
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
    }, []);

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            handleFiles(files);
        }
    };

    const handleFiles = async (files: FileList) => {
        const file = files[0];

        if (!isSupported(file.name)) {
            setUploadStatus({
                type: "error",
                message: "Поддерживаемые форматы: PDF, Word (.docx), Excel (.xlsx), Text (.txt)"
            });
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            setUploadStatus({ type: "error", message: "Размер файла не должен превышать 50MB" });
            return;
        }

        setIsUploading(true);
        setUploadStatus({ type: null, message: "" });

        try {
            const formData = new FormData();
            formData.append("file", file);

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
                filename: file.name,
                original_filename: file.name,
                status: "processing",
                created_at: new Date().toISOString(),
            });

            setProcessingDocs((prev) => [...prev, data.document_id]);
            setProcessingInfo(prev => ({
                ...prev,
                [data.document_id]: { stage: "uploading", progress: 0 }
            }));
            setUploadStatus({ type: "success", message: "Документ загружен! Обработка..." });
        } catch (error) {
            setUploadStatus({
                type: "error",
                message: error instanceof Error ? error.message : "Ошибка загрузки",
            });
        } finally {
            setIsUploading(false);
        }
    };

    // Get the combined processing info for display
    const activeProcessing = processingDocs.map(docId => processingInfo[docId]).filter(Boolean);
    const currentStage = activeProcessing.length > 0 ? activeProcessing[0] : null;

    return (
        <div className="space-y-4">
            <div
                onDragEnter={handleDragIn}
                onDragLeave={handleDragOut}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`upload-zone relative ${isDragging ? "dragover" : ""}`}
            >
                <input
                    type="file"
                    accept={ACCEPT_STRING}
                    onChange={handleFileInput}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
                    disabled={isUploading}
                />

                <div className="relative z-10 flex flex-col items-center gap-4">
                    {isUploading ? (
                        <div className="relative">
                            <div className="absolute inset-0 bg-violet-500 rounded-full blur-xl opacity-30 animate-pulse"></div>
                            <Loader2 className="relative w-10 h-10 text-violet-400 animate-spin" />
                        </div>
                    ) : (
                        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500/15 to-purple-500/10 border border-violet-500/20 flex items-center justify-center">
                            <Upload className="w-6 h-6 text-violet-400" />
                        </div>
                    )}

                    <div>
                        <p className="text-[var(--text-primary)] font-medium">
                            {isUploading ? "Загрузка..." : "Перетащите файл сюда"}
                        </p>
                        <p className="text-[var(--text-tertiary)] text-sm mt-1">
                            PDF, Word, Excel, TXT · до 50MB
                        </p>
                    </div>
                </div>
            </div>

            {uploadStatus.type && (
                <div className={`notification-badge ${uploadStatus.type === "success" ? "success" : "error"}`}>
                    {uploadStatus.type === "success" ? (
                        <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                    ) : (
                        <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    )}
                    <span className={`text-sm ${uploadStatus.type === "success" ? "text-green-400" : "text-red-400"}`}>
                        {uploadStatus.message}
                    </span>
                </div>
            )}

            {processingDocs.length > 0 && (
                <div className="notification-badge processing">
                    <Loader2 className="w-4 h-4 text-violet-400 animate-spin flex-shrink-0" />
                    <div className="flex-1">
                        <p className="text-sm text-violet-300 font-medium">
                            {currentStage
                                ? stageLabels[currentStage.stage] || "Обработка..."
                                : "Обработка..."
                            }
                        </p>
                        <div className="mt-2">
                            <div className="progress-bar">
                                <div
                                    className="progress-fill"
                                    style={{
                                        width: `${currentStage?.progress || 5}%`,
                                        transition: 'width 0.5s ease-in-out'
                                    }}
                                ></div>
                            </div>
                            <p className="text-xs text-[var(--text-tertiary)] mt-1">
                                {currentStage?.progress || 0}%
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
