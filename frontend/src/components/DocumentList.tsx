"use client";

import { useState } from "react";
import { FileText, Eye, FileSpreadsheet, Trash2, AlertTriangle, FileType } from "lucide-react";

interface Document {
    id: number;
    filename: string;
    original_filename: string;
    status: "processing" | "ready" | "failed";
    processing_stage?: string;
    processing_progress?: number;
    error_message?: string;
    page_count?: number;
    chunk_count?: number;
    created_at: string;
}

interface DocumentListProps {
    documents: Document[];
    selectedDocument: Document | null;
    onSelectDocument: (doc: Document) => void;
    onViewFile: () => void;
    onDeleteDocument?: (docId: number) => void;
}

const stageLabels: Record<string, string> = {
    uploading: "Загрузка...",
    checking_ollama: "Проверка AI...",
    extracting_text: "Извлечение текста...",
    chunking: "Разбиение на чанки...",
    generating_embeddings: "Генерация эмбеддингов...",
    storing_vectors: "Сохранение векторов...",
    completed: "Готово",
    failed: "Ошибка"
};

function getFileExtension(filename: string): string {
    return filename.toLowerCase().split(".").pop() || "";
}

function FileIcon({ filename, isReady }: { filename: string; isReady: boolean }) {
    const ext = getFileExtension(filename);

    if (ext === "xlsx") {
        return (
            <FileSpreadsheet
                className={`w-4 h-4 ${isReady ? "text-emerald-400" : "text-[var(--text-tertiary)]"}`}
            />
        );
    }

    if (ext === "txt") {
        return (
            <FileType
                className={`w-4 h-4 ${isReady ? "text-amber-400" : "text-[var(--text-tertiary)]"}`}
            />
        );
    }

    const color = isReady
        ? (ext === "docx" ? "text-blue-400" : "text-violet-400")
        : "text-[var(--text-tertiary)]";

    return <FileText className={`w-4 h-4 ${color}`} />;
}

function getIconContainerStyle(filename: string, isReady: boolean): string {
    if (!isReady) {
        return "bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)]";
    }
    const ext = getFileExtension(filename);
    switch (ext) {
        case "xlsx":
            return "bg-gradient-to-br from-emerald-500/20 to-green-500/10 border border-emerald-500/20";
        case "docx":
            return "bg-gradient-to-br from-blue-500/20 to-sky-500/10 border border-blue-500/20";
        case "txt":
            return "bg-gradient-to-br from-amber-500/20 to-yellow-500/10 border border-amber-500/20";
        default:
            return "bg-gradient-to-br from-violet-500/20 to-purple-500/10 border border-violet-500/20";
    }
}

export default function DocumentList({
    documents,
    selectedDocument,
    onSelectDocument,
    onViewFile,
    onDeleteDocument,
}: DocumentListProps) {
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [showErrorFor, setShowErrorFor] = useState<number | null>(null);

    const handleDelete = async (e: React.MouseEvent, docId: number) => {
        e.stopPropagation();
        if (!confirm("Удалить документ и все его чанки?")) return;

        setDeletingId(docId);
        try {
            const response = await fetch(`/api/documents/${docId}`, {
                method: "DELETE",
            });
            if (response.ok) {
                onDeleteDocument?.(docId);
            }
        } catch (error) {
            console.error("Failed to delete document:", error);
        } finally {
            setDeletingId(null);
        }
    };

    if (documents.length === 0) {
        return (
            <div className="empty-state py-8">
                <div className="w-16 h-16 rounded-2xl bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)] flex items-center justify-center mb-4">
                    <FileText className="w-7 h-7 text-[var(--text-tertiary)]" />
                </div>
                <p className="text-[var(--text-tertiary)] text-sm">Документов пока нет</p>
            </div>
        );
    }

    return (
        <div className="space-y-3 max-h-64 overflow-y-auto">
            {documents.map((doc) => (
                <div
                    key={doc.id}
                    onClick={() => onSelectDocument(doc)}
                    className={`card-3d ${selectedDocument?.id === doc.id ? "selected" : ""}`}
                >
                    <div className="flex items-start gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${getIconContainerStyle(doc.original_filename, doc.status === "ready")}`}>
                            <FileIcon filename={doc.original_filename} isReady={doc.status === "ready"} />
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-[var(--text-primary)] text-sm font-medium truncate">
                                {doc.original_filename}
                            </p>

                            {/* Status and Stage */}
                            <div className="flex items-center gap-2 mt-1.5">
                                <span className={`status-dot ${doc.status === "ready" ? "status-ready" :
                                    doc.status === "processing" ? "status-processing" : "status-failed"
                                    }`}></span>
                                <span className="text-xs text-[var(--text-tertiary)]">
                                    {doc.status === "processing"
                                        ? (stageLabels[doc.processing_stage || "uploading"] || "Обработка...")
                                        : doc.status === "ready"
                                            ? "Готов"
                                            : "Ошибка"
                                    }
                                </span>
                            </div>

                            {/* Progress bar for processing */}
                            {doc.status === "processing" && doc.processing_progress !== undefined && (
                                <div className="mt-2">
                                    <div className="progress-bar">
                                        <div
                                            className="progress-fill"
                                            style={{
                                                width: `${doc.processing_progress}%`,
                                                transition: 'width 0.5s ease-in-out'
                                            }}
                                        ></div>
                                    </div>
                                    <p className="text-xs text-[var(--text-tertiary)] mt-1">
                                        {doc.processing_progress}%
                                    </p>
                                </div>
                            )}

                            {/* Error message for failed documents */}
                            {doc.status === "failed" && doc.error_message && (
                                <div className="mt-1.5">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setShowErrorFor(showErrorFor === doc.id ? null : doc.id);
                                        }}
                                        className="flex items-center gap-1 text-xs text-red-400/80 hover:text-red-400 transition-colors"
                                    >
                                        <AlertTriangle className="w-3 h-3" />
                                        Подробнее
                                    </button>
                                    {showErrorFor === doc.id && (
                                        <p className="text-xs text-red-400/70 mt-1 bg-red-500/5 rounded-lg p-2 border border-red-500/10">
                                            {doc.error_message.slice(0, 300)}
                                        </p>
                                    )}
                                </div>
                            )}

                            {/* Meta info for ready documents */}
                            {doc.status === "ready" && (
                                <div className="flex items-center gap-3 mt-1.5 text-xs text-[var(--text-tertiary)]">
                                    {doc.page_count && <span>{doc.page_count} стр.</span>}
                                    {doc.chunk_count && <span>· {doc.chunk_count} чанков</span>}
                                </div>
                            )}
                        </div>

                        {/* Action buttons */}
                        <div className="flex items-center gap-1">
                            {doc.status === "ready" && selectedDocument?.id === doc.id && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onViewFile();
                                    }}
                                    className="btn-ghost p-2"
                                    title="Просмотр файла"
                                >
                                    <Eye className="w-4 h-4" />
                                </button>
                            )}
                            <button
                                onClick={(e) => handleDelete(e, doc.id)}
                                disabled={deletingId === doc.id}
                                className="btn-ghost p-2 opacity-0 group-hover:opacity-100 hover:!opacity-100 hover:text-red-400 transition-all"
                                title="Удалить документ"
                                style={{ opacity: selectedDocument?.id === doc.id ? 0.6 : 0 }}
                                onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                                onMouseLeave={(e) => (e.currentTarget.style.opacity = selectedDocument?.id === doc.id ? '0.6' : '0')}
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}
