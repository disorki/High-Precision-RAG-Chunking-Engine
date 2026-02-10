"use client";

import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { X, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Loader2 } from "lucide-react";

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PdfViewerProps {
    documentId: number;
    filename: string;
    onClose: () => void;
}

export default function PdfViewer({
    documentId,
    filename,
    onClose,
}: PdfViewerProps) {
    const [numPages, setNumPages] = useState<number | null>(null);
    const [pageNumber, setPageNumber] = useState(1);
    const [scale, setScale] = useState(1.0);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // PDF URL from backend
    const pdfUrl = `/api/uploads/${documentId}`;

    const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
        setNumPages(numPages);
        setIsLoading(false);
    };

    const onDocumentLoadError = (error: Error) => {
        console.error("PDF load error:", error);
        setError("Failed to load PDF. The file may not be available.");
        setIsLoading(false);
    };

    const goToPreviousPage = () => {
        setPageNumber((prev) => Math.max(1, prev - 1));
    };

    const goToNextPage = () => {
        if (numPages) {
            setPageNumber((prev) => Math.min(numPages, prev + 1));
        }
    };

    const zoomIn = () => {
        setScale((prev) => Math.min(2, prev + 0.25));
    };

    const zoomOut = () => {
        setScale((prev) => Math.max(0.5, prev - 0.25));
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-4xl h-[90vh] bg-dark-900 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-dark-700">
                    <h3 className="text-lg font-medium text-dark-100 truncate max-w-md">
                        {filename}
                    </h3>
                    <div className="flex items-center gap-4">
                        {/* Zoom Controls */}
                        <div className="flex items-center gap-2">
                            <button
                                onClick={zoomOut}
                                className="p-2 hover:bg-dark-700 rounded-lg transition-colors text-dark-400 hover:text-dark-200"
                                title="Zoom out"
                            >
                                <ZoomOut className="w-5 h-5" />
                            </button>
                            <span className="text-sm text-dark-400 min-w-[4rem] text-center">
                                {Math.round(scale * 100)}%
                            </span>
                            <button
                                onClick={zoomIn}
                                className="p-2 hover:bg-dark-700 rounded-lg transition-colors text-dark-400 hover:text-dark-200"
                                title="Zoom in"
                            >
                                <ZoomIn className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Page Navigation */}
                        {numPages && (
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={goToPreviousPage}
                                    disabled={pageNumber <= 1}
                                    className="p-2 hover:bg-dark-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors text-dark-400 hover:text-dark-200"
                                >
                                    <ChevronLeft className="w-5 h-5" />
                                </button>
                                <span className="text-sm text-dark-400 min-w-[5rem] text-center">
                                    {pageNumber} / {numPages}
                                </span>
                                <button
                                    onClick={goToNextPage}
                                    disabled={pageNumber >= numPages}
                                    className="p-2 hover:bg-dark-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors text-dark-400 hover:text-dark-200"
                                >
                                    <ChevronRight className="w-5 h-5" />
                                </button>
                            </div>
                        )}

                        {/* Close Button */}
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-dark-700 rounded-lg transition-colors text-dark-400 hover:text-dark-200"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* PDF Content */}
                <div className="flex-1 overflow-auto p-4 flex items-start justify-center bg-dark-800/50">
                    {isLoading && (
                        <div className="flex flex-col items-center justify-center py-12">
                            <Loader2 className="w-10 h-10 text-primary-500 animate-spin mb-4" />
                            <p className="text-dark-400">Loading PDF...</p>
                        </div>
                    )}

                    {error && (
                        <div className="flex flex-col items-center justify-center py-12">
                            <p className="text-red-400 mb-4">{error}</p>
                            <button
                                onClick={onClose}
                                className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-dark-200 rounded-lg transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    )}

                    <Document
                        file={pdfUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        onLoadError={onDocumentLoadError}
                        loading={null}
                        className={isLoading ? "hidden" : ""}
                    >
                        <Page
                            pageNumber={pageNumber}
                            scale={scale}
                            renderTextLayer={false}
                            renderAnnotationLayer={false}
                            className="shadow-xl"
                        />
                    </Document>
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
