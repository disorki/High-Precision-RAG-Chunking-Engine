"use client";

import { FileText, Eye } from "lucide-react";

interface Document {
    id: number;
    filename: string;
    original_filename: string;
    status: "processing" | "ready" | "failed";
    processing_stage?: string;
    processing_progress?: number;
    page_count?: number;
    chunk_count?: number;
    created_at: string;
}

interface DocumentListProps {
    documents: Document[];
    selectedDocument: Document | null;
    onSelectDocument: (doc: Document) => void;
    onViewPdf: () => void;
}

const stageLabels: Record<string, string> = {
    uploading: "Uploading...",
    extracting_text: "Extracting text...",
    chunking: "Chunking document...",
    generating_embeddings: "Generating embeddings...",
    storing_vectors: "Storing vectors...",
    completed: "Completed",
    failed: "Failed"
};

export default function DocumentList({
    documents,
    selectedDocument,
    onSelectDocument,
    onViewPdf,
}: DocumentListProps) {
    if (documents.length === 0) {
        return (
            <div className="empty-state py-8">
                <div className="w-16 h-16 rounded-2xl bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)] flex items-center justify-center mb-4">
                    <FileText className="w-7 h-7 text-[var(--text-tertiary)]" />
                </div>
                <p className="text-[var(--text-tertiary)] text-sm">No documents yet</p>
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
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${doc.status === "ready"
                                ? "bg-gradient-to-br from-violet-500/20 to-purple-500/10 border border-violet-500/20"
                                : "bg-[rgba(255,255,255,0.03)] border border-[var(--border-subtle)]"
                            }`}>
                            <FileText className={`w-4 h-4 ${doc.status === "ready" ? "text-violet-400" : "text-[var(--text-tertiary)]"}`} />
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
                                        ? (stageLabels[doc.processing_stage || "uploading"] || "Processing...")
                                        : doc.status === "ready"
                                            ? "Ready"
                                            : "Failed"
                                    }
                                </span>
                            </div>

                            {/* Progress bar for processing */}
                            {doc.status === "processing" && doc.processing_progress !== undefined && (
                                <div className="mt-2">
                                    <div className="progress-bar">
                                        <div
                                            className="progress-fill"
                                            style={{ width: `${doc.processing_progress}%` }}
                                        ></div>
                                    </div>
                                    <p className="text-xs text-[var(--text-tertiary)] mt-1">
                                        {doc.processing_progress}%
                                    </p>
                                </div>
                            )}

                            {/* Meta info for ready documents */}
                            {doc.status === "ready" && (
                                <div className="flex items-center gap-3 mt-1.5 text-xs text-[var(--text-tertiary)]">
                                    {doc.page_count && <span>{doc.page_count} pages</span>}
                                    {doc.chunk_count && <span>· {doc.chunk_count} chunks</span>}
                                </div>
                            )}
                        </div>
                        {doc.status === "ready" && selectedDocument?.id === doc.id && (
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onViewPdf();
                                }}
                                className="btn-ghost p-2"
                                title="View PDF"
                            >
                                <Eye className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
