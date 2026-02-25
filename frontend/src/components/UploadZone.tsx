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
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            handleFiles(files);
        }
    };

    const handleFiles = async (files: FileList) => {
        // Filter supported files
        const validFiles: File[] = [];
        for (let i = 0; i < files.length; i++) {
            if (isSupported(files[i].name)) {
                validFiles.push(files[i]);
            }
        }

        if (validFiles.length === 0) {
            setUploadStatus({
                type: "error",
                message: "Поддерживаемые форматы: PDF, Word, Excel, TXT, ZIP, RAR"
            });
            return;
        }

        setIsUploading(true);
        setUploadStatus({ type: null, message: "" });

        try {
            if (validFiles.length === 1 && !isArchive(validFiles[0].name)) {
                // Single non-archive file: use the regular single upload endpoint
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
                setUploadStatus({ type: "success", message: "Документ загружен! Обработка..." });
            } else {
                // Multiple files or archives: use batch endpoint
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

                setUploadStatus({
                    type: successCount > 0 ? "success" : "error",
                    message: successCount > 0
                        ? `Загружено ${successCount} файл(ов). Обработка...`
                        : "Не удалось загрузить файлы"
                });
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
                    multiple
                />

                <div className="relative z-10 flex flex-col items-center gap-4">
                    {isUploading ? (
                        <div className="relative">
                            <div style={{
                                position: 'absolute', inset: '-8px', borderRadius: '50%',
                                background: 'rgba(99,102,241,0.22)',
                                filter: 'blur(14px)',
                                animation: 'pulseGlow 1.4s ease-in-out infinite'
                            }} />
                            <Loader2 className="relative w-10 h-10" style={{
                                color: 'var(--accent-secondary)',
                                animation: 'spin 0.9s linear infinite'
                            }} />
                        </div>
                    ) : (
                        <div className="upload-icon-idle" style={{
                            width: 56, height: 56, borderRadius: 18,
                            background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(79,70,229,0.07))',
                            border: '1px solid rgba(99,102,241,0.22)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            boxShadow: '0 0 28px rgba(99,102,241,0.12)'
                        }}>
                            <Upload className="w-6 h-6" style={{ color: 'var(--accent-secondary)' }} />
                        </div>
                    )}

                    <div className="text-center">
                        <p className="text-[var(--text-primary)] font-medium">
                            {isUploading ? "Загрузка..." : "Перетащите файлы сюда"}
                        </p>
                        <p className="text-[var(--text-tertiary)] text-sm mt-1">
                            PDF, Word, Excel, TXT · ZIP, RAR · до 50MB
                        </p>
                        <div className="flex items-center justify-center gap-2 mt-2">
                            <Archive className="w-3.5 h-3.5 text-[var(--text-tertiary)]" />
                            <p className="text-[var(--text-tertiary)] text-xs">
                                Можно загрузить несколько файлов или архив
                            </p>
                        </div>
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
                            {processingDocs.length > 1
                                ? `Обработка ${processingDocs.length} документов...`
                                : currentStage
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
