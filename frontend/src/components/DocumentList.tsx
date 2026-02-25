"use client";

import { useState, useMemo } from "react";
import {
    FileText, Eye, FileSpreadsheet, Trash2, AlertTriangle,
    FileType, X, Search, ArrowUpDown, CheckCircle2,
    Clock, AlertCircle, LayoutList, Loader2
} from "lucide-react";

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
    onDeleteFailed?: () => void;
}

type StatusFilter = "all" | "ready" | "processing" | "failed";
type SortMode = "date" | "name";

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

function formatRelativeDate(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return "только что";
    if (diffMin < 60) return `${diffMin} мин назад`;
    if (diffHour < 24) return `${diffHour} ч назад`;
    if (diffDay === 1) return "вчера";
    if (diffDay < 7) return `${diffDay} дн назад`;
    return date.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function FileIcon({ filename, status }: { filename: string; status: string }) {
    const ext = getFileExtension(filename);
    const isReady = status === "ready";
    const isFailed = status === "failed";

    if (ext === "xlsx") {
        return <FileSpreadsheet className={`w-5 h-5 ${isReady ? "text-emerald-400" : isFailed ? "text-red-400/60" : "text-[var(--text-tertiary)]"}`} />;
    }
    if (ext === "txt") {
        return <FileType className={`w-5 h-5 ${isReady ? "text-amber-400" : isFailed ? "text-red-400/60" : "text-[var(--text-tertiary)]"}`} />;
    }

    const color = isReady
        ? (ext === "docx" ? "text-blue-400" : "text-violet-400")
        : isFailed ? "text-red-400/60" : "text-[var(--text-tertiary)]";
    return <FileText className={`w-5 h-5 ${color}`} />;
}

function getIconBg(filename: string, status: string): string {
    if (status === "failed") return "bg-red-500/8 border border-red-500/15";
    if (status === "processing") return "bg-violet-500/8 border border-violet-500/15";
    const ext = getFileExtension(filename);
    switch (ext) {
        case "xlsx": return "bg-emerald-500/10 border border-emerald-500/15";
        case "docx": return "bg-blue-500/10 border border-blue-500/15";
        case "txt": return "bg-amber-500/10 border border-amber-500/15";
        default: return "bg-violet-500/10 border border-violet-500/15";
    }
}

function StatusBadge({ status }: { status: string }) {
    if (status === "ready") {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <CheckCircle2 className="w-3 h-3" /> Готов
            </span>
        );
    }
    if (status === "processing") {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-violet-500/10 text-violet-400 border border-violet-500/20">
                <Loader2 className="w-3 h-3 animate-spin" /> Обработка
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-red-500/10 text-red-400 border border-red-500/20">
            <AlertCircle className="w-3 h-3" /> Ошибка
        </span>
    );
}

export default function DocumentList({
    documents,
    selectedDocument,
    onSelectDocument,
    onViewFile,
    onDeleteDocument,
    onDeleteFailed,
}: DocumentListProps) {
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [showErrorFor, setShowErrorFor] = useState<number | null>(null);
    const [confirmDeleteDoc, setConfirmDeleteDoc] = useState<Document | null>(null);
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [searchQuery, setSearchQuery] = useState("");
    const [sortMode, setSortMode] = useState<SortMode>("date");

    // Counts by status
    const counts = useMemo(() => ({
        all: documents.length,
        ready: documents.filter(d => d.status === "ready").length,
        processing: documents.filter(d => d.status === "processing").length,
        failed: documents.filter(d => d.status === "failed").length,
    }), [documents]);

    // Filtered + sorted documents
    const filteredDocs = useMemo(() => {
        let results = documents;

        // Status filter
        if (statusFilter !== "all") {
            results = results.filter(d => d.status === statusFilter);
        }

        // Search filter
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            results = results.filter(d =>
                d.original_filename.toLowerCase().includes(q)
            );
        }

        // Sort
        results = [...results].sort((a, b) => {
            if (sortMode === "name") {
                return a.original_filename.localeCompare(b.original_filename);
            }
            return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });

        return results;
    }, [documents, statusFilter, searchQuery, sortMode]);

    const handleDelete = async (doc: Document) => {
        setConfirmDeleteDoc(null);
        setDeletingId(doc.id);
        try {
            const response = await fetch(`/api/documents/${doc.id}`, {
                method: "DELETE",
            });
            if (response.ok) {
                onDeleteDocument?.(doc.id);
            } else {
                const data = await response.json().catch(() => null);
                console.error("Delete failed:", response.status, data);
            }
        } catch (error) {
            console.error("Failed to delete document:", error);
        } finally {
            setDeletingId(null);
        }
    };

    const handleDeleteAllFailed = async () => {
        try {
            const response = await fetch("/api/documents/failed", {
                method: "DELETE",
            });
            if (response.ok) {
                onDeleteFailed?.();
            }
        } catch (error) {
            console.error("Failed to delete failed documents:", error);
        }
    };

    const filterTabs: { key: StatusFilter; label: string; icon: React.ReactNode }[] = [
        { key: "all", label: "Все", icon: <LayoutList className="w-3.5 h-3.5" /> },
        { key: "ready", label: "Готовы", icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
        { key: "processing", label: "В работе", icon: <Clock className="w-3.5 h-3.5" /> },
        { key: "failed", label: "Ошибки", icon: <AlertCircle className="w-3.5 h-3.5" /> },
    ];

    if (documents.length === 0) {
        return (
            <div className="empty-state py-8">
                <div className="w-16 h-16 rounded-2xl bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)] flex items-center justify-center mb-4">
                    <FileText className="w-7 h-7 text-[var(--text-tertiary)]" />
                </div>
                <p className="text-[var(--text-tertiary)] text-sm">Документов пока нет</p>
                <p className="text-[var(--text-tertiary)] text-xs mt-1 opacity-60">Загрузите файлы через зону выше</p>
            </div>
        );
    }

    const emptyMessages: Record<StatusFilter, string> = {
        all: "Документов не найдено",
        ready: "Нет готовых документов",
        processing: "Нет документов в обработке",
        failed: "Нет документов с ошибками",
    };

    return (
        <>
            {/* Filter Tabs */}
            <div className="flex gap-1 p-1 mb-3 bg-[rgba(255,255,255,0.02)] rounded-xl border border-[var(--border-subtle)]">
                {filterTabs.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setStatusFilter(tab.key)}
                        className={`doc-filter-tab ${statusFilter === tab.key ? "active" : ""}`}
                    >
                        {tab.icon}
                        <span>{tab.label}</span>
                        {counts[tab.key] > 0 && (
                            <span className={`doc-filter-count ${statusFilter === tab.key ? "active" : ""}`}>
                                {counts[tab.key]}
                            </span>
                        )}
                    </button>
                ))}
            </div>

            {/* Search + Sort */}
            <div className="flex gap-2 mb-3">
                <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-tertiary)]" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Поиск по имени..."
                        className="w-full pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)] rounded-lg outline-none focus:border-[var(--accent-primary)] transition-colors placeholder:text-[var(--text-tertiary)]"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                        >
                            <X className="w-3.5 h-3.5" />
                        </button>
                    )}
                </div>
                <button
                    onClick={() => setSortMode(s => s === "date" ? "name" : "date")}
                    className="flex items-center gap-1.5 px-3 py-2 text-xs text-[var(--text-tertiary)] bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)] rounded-lg hover:border-[var(--border-default)] hover:text-[var(--text-secondary)] transition-all"
                    title={sortMode === "date" ? "Сортировка: по дате" : "Сортировка: по имени"}
                >
                    <ArrowUpDown className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">{sortMode === "date" ? "Дата" : "Имя"}</span>
                </button>
            </div>

            {/* Batch delete for failed */}
            {statusFilter === "failed" && counts.failed > 0 && (
                <button
                    onClick={handleDeleteAllFailed}
                    className="w-full mb-3 flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-red-400 bg-red-500/5 border border-red-500/15 rounded-lg hover:bg-red-500/10 hover:border-red-500/25 transition-all"
                >
                    <Trash2 className="w-3.5 h-3.5" />
                    Удалить все с ошибкой ({counts.failed})
                </button>
            )}

            {/* Document Cards */}
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 doc-list-scroll">
                {filteredDocs.length === 0 ? (
                    <div className="text-center py-8">
                        <Search className="w-8 h-8 text-[var(--text-tertiary)] mx-auto mb-3 opacity-40" />
                        <p className="text-[var(--text-tertiary)] text-sm">{emptyMessages[statusFilter]}</p>
                        {searchQuery && (
                            <p className="text-[var(--text-tertiary)] text-xs mt-1 opacity-60">
                                Попробуйте изменить запрос
                            </p>
                        )}
                    </div>
                ) : (
                    filteredDocs.map((doc) => (
                        <div
                            key={doc.id}
                            onClick={() => onSelectDocument(doc)}
                            className={`doc-card group ${selectedDocument?.id === doc.id ? "doc-card-selected" : ""} ${doc.status === "failed" ? "doc-card-failed" : ""} ${deletingId === doc.id ? "opacity-40 pointer-events-none" : ""}`}
                        >
                            <div className="flex items-start gap-3">
                                {/* File icon */}
                                <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${getIconBg(doc.original_filename, doc.status)}`}>
                                    <FileIcon filename={doc.original_filename} status={doc.status} />
                                </div>

                                {/* Content */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <p className="text-[var(--text-primary)] text-sm font-medium truncate flex-1">
                                            {doc.original_filename}
                                        </p>
                                        <span className="text-[10px] text-[var(--text-tertiary)] flex-shrink-0 opacity-60">
                                            {formatRelativeDate(doc.created_at)}
                                        </span>
                                    </div>

                                    {/* Status + meta row */}
                                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                                        <StatusBadge status={doc.status} />

                                        {doc.status === "ready" && (
                                            <>
                                                {doc.page_count != null && doc.page_count > 0 && (
                                                    <span className="doc-meta-pill">
                                                        {doc.page_count} стр.
                                                    </span>
                                                )}
                                                {doc.chunk_count != null && doc.chunk_count > 0 && (
                                                    <span className="doc-meta-pill">
                                                        {doc.chunk_count} чанков
                                                    </span>
                                                )}
                                            </>
                                        )}
                                    </div>

                                    {/* Processing progress */}
                                    {doc.status === "processing" && (
                                        <div className="mt-2">
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="text-[10px] text-violet-400/80">
                                                    {stageLabels[doc.processing_stage || "uploading"] || "Обработка..."}
                                                </span>
                                                {doc.processing_progress !== undefined && (
                                                    <span className="text-[10px] text-violet-400 font-mono font-semibold">
                                                        {doc.processing_progress}%
                                                    </span>
                                                )}
                                            </div>
                                            <div className="progress-bar">
                                                <div
                                                    className="progress-fill"
                                                    style={{
                                                        width: `${doc.processing_progress || 0}%`,
                                                        transition: "width 0.5s ease-in-out"
                                                    }}
                                                ></div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Error message */}
                                    {doc.status === "failed" && doc.error_message && (
                                        <div className="mt-1.5">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setShowErrorFor(showErrorFor === doc.id ? null : doc.id);
                                                }}
                                                className="flex items-center gap-1 text-[11px] text-red-400/70 hover:text-red-400 transition-colors"
                                            >
                                                <AlertTriangle className="w-3 h-3" />
                                                {showErrorFor === doc.id ? "Скрыть" : "Подробнее"}
                                            </button>
                                            {showErrorFor === doc.id && (
                                                <p className="text-[11px] text-red-400/60 mt-1.5 bg-red-500/5 rounded-lg p-2.5 border border-red-500/10 leading-relaxed">
                                                    {doc.error_message.slice(0, 300)}
                                                </p>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* Action toolbar */}
                                <div className="flex flex-col items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                    {doc.status === "ready" && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onSelectDocument(doc);
                                                onViewFile();
                                            }}
                                            className="doc-action-btn"
                                            title="Просмотр файла"
                                        >
                                            <Eye className="w-3.5 h-3.5" />
                                        </button>
                                    )}
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setConfirmDeleteDoc(doc);
                                        }}
                                        disabled={deletingId === doc.id}
                                        className="doc-action-btn doc-action-delete"
                                        title="Удалить"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Custom Delete Confirmation Modal */}
            {confirmDeleteDoc && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center"
                    style={{ backgroundColor: "rgba(0, 0, 0, 0.6)", backdropFilter: "blur(4px)" }}
                    onClick={() => setConfirmDeleteDoc(null)}
                >
                    <div
                        className="glass-card p-6 max-w-sm w-full mx-4 shadow-2xl"
                        style={{
                            border: "1px solid rgba(255,255,255,0.1)",
                            animation: "fadeIn 0.15s ease-out"
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                                    <Trash2 className="w-5 h-5 text-red-400" />
                                </div>
                                <h3 className="text-lg font-semibold text-[var(--text-primary)]">
                                    Удалить документ?
                                </h3>
                            </div>
                            <button onClick={() => setConfirmDeleteDoc(null)} className="btn-ghost p-1.5 rounded-lg">
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        <p className="text-sm text-[var(--text-secondary)] mb-2">
                            Будет удалён документ и все связанные данные:
                        </p>
                        <div className="bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)] rounded-lg p-3 mb-5">
                            <p className="text-sm text-[var(--text-primary)] font-medium truncate">
                                {confirmDeleteDoc.original_filename}
                            </p>
                            <p className="text-xs text-[var(--text-tertiary)] mt-1">
                                Чанки, история чата и файл будут удалены безвозвратно
                            </p>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => setConfirmDeleteDoc(null)}
                                className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-[var(--text-secondary)] bg-[rgba(255,255,255,0.05)] border border-[var(--border-subtle)] hover:bg-[rgba(255,255,255,0.08)] transition-colors"
                            >
                                Отмена
                            </button>
                            <button
                                onClick={() => handleDelete(confirmDeleteDoc)}
                                className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-white bg-red-500/80 hover:bg-red-500 border border-red-500/30 transition-colors"
                            >
                                Удалить
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
