"use client";

import { useState } from "react";
import { X, Download, Loader2, FileText, FileSpreadsheet, FileType } from "lucide-react";

interface FileViewerProps {
    documentId: number;
    filename: string;
    onClose: () => void;
}

function getFileExtension(filename: string): string {
    return filename.toLowerCase().split(".").pop() || "";
}

export default function FileViewer({
    documentId,
    filename,
    onClose,
}: FileViewerProps) {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fileUrl = `/api/documents/${documentId}/file`;
    const ext = getFileExtension(filename);
    const isPdf = ext === "pdf";
    const isTxt = ext === "txt";

    const handleIframeLoad = () => {
        setIsLoading(false);
    };

    const handleIframeError = () => {
        setError("Не удалось загрузить файл для предпросмотра.");
        setIsLoading(false);
    };

    const handleDownload = () => {
        const a = document.createElement("a");
        a.href = fileUrl;
        a.download = filename;
        a.click();
    };

    const getFileIcon = () => {
        switch (ext) {
            case "xlsx":
                return <FileSpreadsheet className="w-16 h-16 text-emerald-400" />;
            case "docx":
                return <FileText className="w-16 h-16 text-blue-400" />;
            case "txt":
                return <FileType className="w-16 h-16 text-amber-400" />;
            default:
                return <FileText className="w-16 h-16 text-violet-400" />;
        }
    };

    const getFileTypeLabel = () => {
        switch (ext) {
            case "pdf": return "PDF";
            case "docx": return "Word";
            case "xlsx": return "Excel";
            case "txt": return "Text";
            default: return "Документ";
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-4xl h-[90vh] bg-dark-900 rounded-2xl shadow-2xl flex flex-col overflow-hidden"
                style={{ backgroundColor: 'var(--bg-primary, #0a0a0f)' }}>
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-dark-700"
                    style={{ borderColor: 'var(--border-subtle, rgba(255,255,255,0.06))' }}>
                    <div className="flex items-center gap-3 min-w-0">
                        <span className="px-2 py-0.5 rounded text-xs font-medium"
                            style={{
                                backgroundColor: ext === 'xlsx' ? 'rgba(16,185,129,0.15)' :
                                    ext === 'docx' ? 'rgba(59,130,246,0.15)' :
                                        ext === 'txt' ? 'rgba(245,158,11,0.15)' :
                                            'rgba(139,92,246,0.15)',
                                color: ext === 'xlsx' ? '#34d399' :
                                    ext === 'docx' ? '#60a5fa' :
                                        ext === 'txt' ? '#fbbf24' :
                                            '#a78bfa'
                            }}>
                            {getFileTypeLabel()}
                        </span>
                        <h3 className="text-lg font-medium truncate max-w-md"
                            style={{ color: 'var(--text-primary, #e4e4e7)' }}>
                            {filename}
                        </h3>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleDownload}
                            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors"
                            style={{
                                backgroundColor: 'rgba(255,255,255,0.05)',
                                color: 'var(--text-secondary, #a1a1aa)'
                            }}
                            title="Скачать файл"
                        >
                            <Download className="w-4 h-4" />
                            Скачать
                        </button>
                        <button
                            onClick={onClose}
                            className="p-2 rounded-lg transition-colors"
                            style={{ color: 'var(--text-tertiary, #71717a)' }}
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto flex items-center justify-center"
                    style={{ backgroundColor: 'rgba(0,0,0,0.3)' }}>

                    {isLoading && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center z-10"
                            style={{ backgroundColor: 'var(--bg-primary, #0a0a0f)' }}>
                            <Loader2 className="w-10 h-10 text-violet-500 animate-spin mb-4" />
                            <p style={{ color: 'var(--text-tertiary, #71717a)' }}>
                                Загрузка {getFileTypeLabel()}...
                            </p>
                        </div>
                    )}

                    {error && (
                        <div className="flex flex-col items-center justify-center py-12">
                            <p className="text-red-400 mb-4">{error}</p>
                            <button
                                onClick={handleDownload}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors"
                                style={{
                                    backgroundColor: 'rgba(255,255,255,0.05)',
                                    color: 'var(--text-secondary, #a1a1aa)'
                                }}
                            >
                                <Download className="w-4 h-4" />
                                Скачать файл
                            </button>
                        </div>
                    )}

                    {isPdf ? (
                        /* PDF — render in iframe */
                        <iframe
                            src={fileUrl}
                            className="w-full h-full border-0"
                            onLoad={handleIframeLoad}
                            onError={handleIframeError}
                            title={filename}
                        />
                    ) : isTxt ? (
                        /* TXT — render in iframe */
                        <iframe
                            src={fileUrl}
                            className="w-full h-full border-0"
                            style={{ backgroundColor: '#1a1a2e', color: '#e4e4e7' }}
                            onLoad={handleIframeLoad}
                            onError={handleIframeError}
                            title={filename}
                        />
                    ) : (
                        /* DOCX/XLSX — show download prompt with icon */
                        !error && (
                            <div className="flex flex-col items-center justify-center py-16 px-8 text-center"
                                onLoad={() => setIsLoading(false)}
                                ref={(el) => { if (el) setIsLoading(false); }}>
                                <div className="mb-6 p-6 rounded-2xl"
                                    style={{ backgroundColor: 'rgba(255,255,255,0.03)' }}>
                                    {getFileIcon()}
                                </div>
                                <h4 className="text-xl font-semibold mb-2"
                                    style={{ color: 'var(--text-primary, #e4e4e7)' }}>
                                    {filename}
                                </h4>
                                <p className="mb-6 max-w-sm"
                                    style={{ color: 'var(--text-tertiary, #71717a)' }}>
                                    Предпросмотр {getFileTypeLabel()} в браузере не поддерживается.
                                    Скачайте файл чтобы открыть его.
                                </p>
                                <button
                                    onClick={handleDownload}
                                    className="flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all"
                                    style={{
                                        background: 'linear-gradient(135deg, #8b5cf6, #7c3aed)',
                                        color: 'white',
                                        boxShadow: '0 4px 15px rgba(139,92,246,0.3)'
                                    }}
                                >
                                    <Download className="w-5 h-5" />
                                    Скачать {getFileTypeLabel()}
                                </button>
                            </div>
                        )
                    )}
                </div>
            </div>

            {/* Click outside to close */}
            <div
                className="absolute inset-0 -z-10"
                onClick={onClose}
            />
        </div>
    );
}
