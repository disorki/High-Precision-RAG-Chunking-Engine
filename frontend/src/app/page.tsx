"use client";

import { useState, useCallback, useEffect } from "react";
import { FileText, Upload, MessageSquare, Sparkles, Zap, Shield, Cpu } from "lucide-react";
import UploadZone from "@/components/UploadZone";
import DocumentList from "@/components/DocumentList";
import ChatInterface from "@/components/ChatInterface";
import PdfViewer from "@/components/PdfViewer";

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

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
}

interface ChatState {
    messages: Message[];
    sessionId: number | null;
}

export default function Home() {
    const [documents, setDocuments] = useState<Document[]>([]);
    const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
    const [activeTab, setActiveTab] = useState<"upload" | "chat">("upload");
    const [showPdf, setShowPdf] = useState(false);
    const [chatStateMap, setChatStateMap] = useState<Record<number, ChatState>>({});
    const [isLoading, setIsLoading] = useState(true);

    // Load documents from API on mount
    useEffect(() => {
        const fetchDocuments = async () => {
            try {
                const response = await fetch("/api/documents");
                if (response.ok) {
                    const data = await response.json();
                    setDocuments(data);
                    // Auto-select the first ready document if any
                    const readyDoc = data.find((d: Document) => d.status === "ready");
                    if (readyDoc) {
                        setSelectedDocument(readyDoc);
                        setActiveTab("chat");
                    }
                }
            } catch (error) {
                console.error("Failed to fetch documents:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchDocuments();
    }, []);

    // Poll for processing documents status
    useEffect(() => {
        const processingDocs = documents.filter(d => d.status === "processing");
        if (processingDocs.length === 0) return;

        const interval = setInterval(async () => {
            for (const doc of processingDocs) {
                try {
                    const response = await fetch(`/api/documents/${doc.id}`);
                    if (response.ok) {
                        const updatedDoc = await response.json();
                        setDocuments(prev => prev.map(d =>
                            d.id === updatedDoc.id ? updatedDoc : d
                        ));
                        // Update selected document if it's the same
                        if (selectedDocument?.id === updatedDoc.id) {
                            setSelectedDocument(updatedDoc);
                        }
                        // Switch to chat when ready
                        if (updatedDoc.status === "ready" && selectedDocument?.id === updatedDoc.id) {
                            setActiveTab("chat");
                        }
                    }
                } catch (error) {
                    console.error("Error polling document status:", error);
                }
            }
        }, 1500);

        return () => clearInterval(interval);
    }, [documents, selectedDocument]);

    const currentChatState = selectedDocument ? chatStateMap[selectedDocument.id] : null;

    const handleMessagesChange = useCallback((messages: Message[], sessionId: number | null) => {
        if (selectedDocument) {
            setChatStateMap(prev => ({
                ...prev,
                [selectedDocument.id]: { messages, sessionId }
            }));
        }
    }, [selectedDocument]);

    const handleDocumentUploaded = (doc: Document) => {
        setDocuments(prev => [doc, ...prev]);
        setSelectedDocument(doc);
    };

    const handleDocumentReady = (docId: number, pageCount: number) => {
        setDocuments(prev =>
            prev.map(d =>
                d.id === docId ? { ...d, status: "ready" as const, page_count: pageCount } : d
            )
        );
        setActiveTab("chat");
    };

    const handleSelectDocument = (doc: Document) => {
        setSelectedDocument(doc);
        if (doc.status === "ready") {
            setActiveTab("chat");
        }
    };

    const handleDeleteDocument = (docId: number) => {
        setDocuments(prev => prev.filter(d => d.id !== docId));
        if (selectedDocument?.id === docId) {
            setSelectedDocument(null);
            setActiveTab("upload");
        }
        // Clean up chat state for deleted document
        setChatStateMap(prev => {
            const next = { ...prev };
            delete next[docId];
            return next;
        });
    };

    return (
        <main className="min-h-screen relative">
            {/* Aurora Background */}
            <div className="aurora-bg">
                <div className="gradient-orb gradient-orb-1"></div>
                <div className="gradient-orb gradient-orb-2"></div>
                <div className="gradient-orb gradient-orb-3"></div>
            </div>

            <div className="relative z-10 p-4 md:p-8">
                {/* Header */}
                <header className="max-w-7xl mx-auto mb-8 animate-in">
                    <div className="glass-card p-6 md:p-8">
                        <div className="flex items-center gap-5">
                            <div className="icon-container">
                                <Cpu className="w-6 h-6 text-white" />
                            </div>
                            <div>
                                <h1 className="text-2xl md:text-3xl font-bold gradient-text">
                                    Intelligent RAG System
                                </h1>
                                <p className="text-[var(--text-secondary)] text-sm md:text-base mt-1">
                                    AI-powered document analysis and retrieval
                                </p>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Main Content */}
                <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Panel - Documents */}
                    <div className="lg:col-span-1 space-y-6">
                        {/* Upload Zone */}
                        <div className="glass-card p-6 animate-in" style={{ animationDelay: '100ms' }}>
                            <div className="flex items-center gap-3 mb-5">
                                <div className="icon-container-sm bg-gradient-to-br from-violet-500 to-purple-600" style={{ width: '40px', height: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '12px' }}>
                                    <Upload className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                                        Upload Document
                                    </h2>
                                    <p className="text-xs text-[var(--text-tertiary)]">PDF, Word, Excel, TXT · до 50MB</p>
                                </div>
                            </div>
                            <UploadZone
                                onDocumentUploaded={handleDocumentUploaded}
                                onDocumentReady={handleDocumentReady}
                            />
                        </div>

                        {/* Document List */}
                        <div className="glass-card p-6 animate-in" style={{ animationDelay: '200ms' }}>
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                                    Your Documents
                                </h2>
                                {documents.length > 0 && (
                                    <span className="text-xs text-[var(--text-tertiary)] bg-[var(--bg-elevated)] px-2.5 py-1 rounded-full">
                                        {documents.length}
                                    </span>
                                )}
                            </div>
                            <DocumentList
                                documents={documents}
                                selectedDocument={selectedDocument}
                                onSelectDocument={handleSelectDocument}
                                onViewFile={() => setShowPdf(true)}
                                onDeleteDocument={handleDeleteDocument}
                            />
                        </div>
                    </div>

                    {/* Right Panel - Chat */}
                    <div className="lg:col-span-2 animate-in" style={{ animationDelay: '300ms' }}>
                        <div className="glass-card overflow-hidden h-[calc(100vh-12rem)]">
                            {/* Tabs */}
                            <div className="p-4 border-b border-[var(--border-subtle)]">
                                <div className="tab-nav">
                                    <button
                                        onClick={() => setActiveTab("upload")}
                                        className={`tab-item ${activeTab === "upload" ? "active" : ""}`}
                                    >
                                        <Sparkles className="w-4 h-4" />
                                        Getting Started
                                    </button>
                                    <button
                                        onClick={() => setActiveTab("chat")}
                                        className={`tab-item ${activeTab === "chat" ? "active" : ""}`}
                                    >
                                        <MessageSquare className="w-4 h-4" />
                                        Chat
                                    </button>
                                </div>
                            </div>

                            {/* Tab Content */}
                            <div className="h-[calc(100%-81px)]">
                                {activeTab === "upload" ? (
                                    <div className="flex flex-col items-center justify-center h-full p-8">
                                        <div className="empty-state">
                                            <div className="empty-state-icon">
                                                <FileText className="w-10 h-10 text-violet-400" />
                                            </div>
                                            <h3 className="text-2xl font-bold text-[var(--text-primary)] mb-3">
                                                Welcome to RAG Chat
                                            </h3>
                                            <p className="text-[var(--text-secondary)] max-w-md mb-10">
                                                Upload a document and start asking questions. Our AI will analyze and provide accurate answers with sources.
                                            </p>

                                            <div className="w-full max-w-md space-y-4">
                                                <div className="feature-card">
                                                    <div className="feature-icon">
                                                        <Upload className="w-5 h-5 text-violet-400" />
                                                    </div>
                                                    <div>
                                                        <p className="font-medium text-[var(--text-primary)]">Загрузить документ</p>
                                                        <p className="text-sm text-[var(--text-tertiary)]">Перетащите или выберите файл</p>
                                                    </div>
                                                </div>

                                                <div className="feature-card">
                                                    <div className="feature-icon">
                                                        <Zap className="w-5 h-5 text-violet-400" />
                                                    </div>
                                                    <div>
                                                        <p className="font-medium text-[var(--text-primary)]">AI Processing</p>
                                                        <p className="text-sm text-[var(--text-tertiary)]">Smart chunking & embedding</p>
                                                    </div>
                                                </div>

                                                <div className="feature-card">
                                                    <div className="feature-icon">
                                                        <Shield className="w-5 h-5 text-violet-400" />
                                                    </div>
                                                    <div>
                                                        <p className="font-medium text-[var(--text-primary)]">Accurate Answers</p>
                                                        <p className="text-sm text-[var(--text-tertiary)]">With source citations</p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    <ChatInterface
                                        document={selectedDocument}
                                        onNoDocument={() => setActiveTab("upload")}
                                        messages={currentChatState?.messages || []}
                                        sessionId={currentChatState?.sessionId || null}
                                        onMessagesChange={handleMessagesChange}
                                    />
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* PDF Viewer Modal */}
            {showPdf && selectedDocument && (
                <FileViewer
                    documentId={selectedDocument.id}
                    filename={selectedDocument.original_filename}
                    onClose={() => setShowPdf(false)}
                />
            )}
        </main>
    );
}
