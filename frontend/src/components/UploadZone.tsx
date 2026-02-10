"use client";

import { useCallback, useState, useEffect } from "react";
import { Upload, CheckCircle, XCircle, Loader2 } from "lucide-react";

interface Document {
    id: number;
    filename: string;
    original_filename: string;
    status: "processing" | "ready" | "failed";
    page_count?: number;
    created_at: string;
}

interface UploadZoneProps {
    onDocumentUploaded: (doc: Document) => void;
    onDocumentReady: (docId: number) => void;
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

    useEffect(() => {
        if (processingDocs.length === 0) return;

        const interval = setInterval(async () => {
            for (const docId of processingDocs) {
                try {
                    const response = await fetch(`/api/documents/${docId}`);
                    if (response.ok) {
                        const doc = await response.json();
                        if (doc.status === "ready") {
                            onDocumentReady(docId);
                            setProcessingDocs((prev) => prev.filter((id) => id !== docId));
                        } else if (doc.status === "failed") {
                            setProcessingDocs((prev) => prev.filter((id) => id !== docId));
                            setUploadStatus({
                                type: "error",
                                message: `Processing failed: ${doc.error_message || "Unknown error"}`,
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

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            setUploadStatus({ type: "error", message: "Only PDF files are supported" });
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            setUploadStatus({ type: "error", message: "File size must be less than 50MB" });
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
            setUploadStatus({ type: "success", message: "Document uploaded! Processing..." });
        } catch (error) {
            setUploadStatus({
                type: "error",
                message: error instanceof Error ? error.message : "Upload failed",
            });
        } finally {
            setIsUploading(false);
        }
    };

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
                    accept=".pdf"
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
                            {isUploading ? "Uploading..." : "Drop PDF here"}
                        </p>
                        <p className="text-[var(--text-tertiary)] text-sm mt-1">
                            or click to browse
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
                            Processing {processingDocs.length} document(s)
                        </p>
                        <div className="mt-2">
                            <div className="progress-bar">
                                <div className="progress-fill" style={{ width: '66%' }}></div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
