"use client";

import { useState, useCallback, useEffect } from "react";
import { FileText, Upload, MessageSquare, Sparkles, Zap, Globe, Database } from "lucide-react";
import UploadZone from "@/components/UploadZone";
import DocumentList from "@/components/DocumentList";
import ChatInterface from "@/components/ChatInterface";
import FileViewer from "@/components/FileViewer";
import SyncSourcePanel from "@/components/SyncSourcePanel";

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
    const [activeTab, setActiveTab] = useState<"upload" | "chat" | "global">("upload");
    const [showPdf, setShowPdf] = useState(false);
    const [chatStateMap, setChatStateMap] = useState<Record<string, ChatState>>({});
    const [isLoading, setIsLoading] = useState(true);

    const GLOBAL_CHAT_KEY = "__global__";

    useEffect(() => {
        const fetchDocuments = async () => {
            try {
                const response = await fetch("/api/documents");
                if (response.ok) {
                    const data = await response.json();
                    setDocuments(data);
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
                        if (selectedDocument?.id === updatedDoc.id) {
                            setSelectedDocument(updatedDoc);
                        }
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

    const currentDocChatState = selectedDocument ? chatStateMap[String(selectedDocument.id)] : null;
    const globalChatState = chatStateMap[GLOBAL_CHAT_KEY] || null;

    const handleDocMessagesChange = useCallback((messages: Message[], sessionId: number | null) => {
        if (selectedDocument) {
            setChatStateMap(prev => ({
                ...prev,
                [String(selectedDocument.id)]: { messages, sessionId }
            }));
        }
    }, [selectedDocument]);

    const handleGlobalMessagesChange = useCallback((messages: Message[], sessionId: number | null) => {
        setChatStateMap(prev => ({
            ...prev,
            [GLOBAL_CHAT_KEY]: { messages, sessionId }
        }));
    }, [GLOBAL_CHAT_KEY]);

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
        setChatStateMap(prev => {
            const next = { ...prev };
            delete next[String(docId)];
            return next;
        });
    };

    const handleDeleteFailed = () => {
        const failedIds = documents.filter(d => d.status === "failed").map(d => d.id);
        setDocuments(prev => prev.filter(d => d.status !== "failed"));
        if (selectedDocument && failedIds.includes(selectedDocument.id)) {
            setSelectedDocument(null);
            setActiveTab("upload");
        }
        setChatStateMap(prev => {
            const next = { ...prev };
            failedIds.forEach(id => delete next[String(id)]);
            return next;
        });
    };

    const tabs = [
        { key: "upload" as const, label: "Обзор", icon: <Sparkles className="w-3.5 h-3.5" /> },
        { key: "chat" as const, label: "Документ", icon: <MessageSquare className="w-3.5 h-3.5" /> },
        { key: "global" as const, label: "Все документы", icon: <Globe className="w-3.5 h-3.5" /> },
    ];

    return (
        <main className="min-h-screen relative">
            {/* Aurora Background */}
            <div className="aurora-bg">
                <div className="gradient-orb gradient-orb-1" />
                <div className="gradient-orb gradient-orb-2" />
                <div className="gradient-orb gradient-orb-3" />
            </div>

            <div className="relative z-10 px-4 lg:px-6 py-3">
                {/* ── Header ── */}
                <header
                    className="max-w-[1920px] mx-auto mb-3"
                    style={{ animation: "slideInUp 0.5s cubic-bezier(0.16,1,0.3,1) both" }}
                >
                    <div className="flex items-center gap-3">
                        {/* Logo mark */}
                        <div style={{
                            width: 36, height: 36, borderRadius: 11, flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
                            boxShadow: '0 4px 18px rgba(99,102,241,0.42), inset 0 1px 0 rgba(255,255,255,0.18)'
                        }}>
                            <Database className="w-4.5 h-4.5 text-white" style={{ width: 18, height: 18 }} />
                        </div>
                        <div>
                            <h1 className="text-base font-bold leading-tight" style={{
                                fontFamily: "'Plus Jakarta Sans', Inter, sans-serif",
                                background: 'linear-gradient(135deg, #e0e7ff 0%, #a5b4fc 60%, #818cf8 100%)',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                                backgroundClip: 'text'
                            }}>
                                RAG System
                            </h1>
                            <p className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                                Анализ документов с AI
                            </p>
                        </div>

                        {/* Status badge */}
                        <div style={{
                            marginLeft: 'auto',
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '4px 10px', borderRadius: 100,
                            background: 'rgba(16,185,129,0.08)',
                            border: '1px solid rgba(16,185,129,0.20)',
                        }}>
                            <span className="status-dot status-ready" style={{ width: 6, height: 6 }} />
                            <span className="text-[10px] font-medium" style={{ color: '#34d399' }}>
                                {documents.filter(d => d.status === "ready").length} документов
                            </span>
                        </div>
                    </div>
                </header>

                {/* ── Main 2-column grid ── */}
                <div className="max-w-[1920px] mx-auto grid grid-cols-1 lg:grid-cols-[340px_1fr] xl:grid-cols-[360px_1fr] gap-3">

                    {/* ═══ Left Panel ═══ */}
                    <div className="lg:col-span-1 space-y-3 lg:max-h-[calc(100vh-4.5rem)] lg:overflow-y-auto lg:pr-1">

                        {/* Upload */}
                        <div
                            className="glass-card p-4"
                            style={{ animation: "slideInUp 0.55s cubic-bezier(0.16,1,0.3,1) 60ms both" }}
                        >
                            <UploadZone
                                onDocumentUploaded={handleDocumentUploaded}
                                onDocumentReady={handleDocumentReady}
                            />
                        </div>

                        {/* Documents */}
                        <div
                            className="glass-card p-4"
                            style={{ animation: "slideInUp 0.55s cubic-bezier(0.16,1,0.3,1) 120ms both" }}
                        >
                            <div className="flex items-center justify-between mb-3">
                                <h2 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                                    Документы
                                </h2>
                                {documents.length > 0 && (
                                    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{
                                        color: 'var(--accent-secondary)',
                                        background: 'rgba(99,102,241,0.10)',
                                        border: '1px solid rgba(99,102,241,0.18)'
                                    }}>
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
                                onDeleteFailed={handleDeleteFailed}
                            />
                        </div>

                        {/* Yandex Disk */}
                        <div style={{ animation: "slideInUp 0.55s cubic-bezier(0.16,1,0.3,1) 180ms both" }}>
                            <SyncSourcePanel onDocumentUploaded={handleDocumentUploaded} existingDocuments={documents} />
                        </div>
                    </div>

                    {/* ═══ Right Panel — Chat ═══ */}
                    <div style={{ animation: "slideInUp 0.6s cubic-bezier(0.16,1,0.3,1) 200ms both" }}>
                        <div className="glass-card overflow-hidden h-[calc(100vh-4.5rem)] flex flex-col">

                            {/* Tabs */}
                            <div className="px-4 pt-2">
                                <div className="tab-nav">
                                    {tabs.map(tab => (
                                        <button
                                            key={tab.key}
                                            onClick={() => setActiveTab(tab.key)}
                                            className={`tab-item ${activeTab === tab.key ? "active" : ""}`}
                                        >
                                            {tab.icon}
                                            {tab.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-h-0">
                                {activeTab === "upload" ? (
                                    <div className="flex flex-col items-center justify-center h-full p-6">
                                        <div className="text-center max-w-sm">
                                            {/* Hero icon */}
                                            <div className="empty-state-icon mx-auto mb-5" style={{
                                                width: 72, height: 72, borderRadius: 22,
                                                background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(79,70,229,0.08))',
                                                border: '1px solid rgba(99,102,241,0.22)',
                                                boxShadow: '0 0 40px rgba(99,102,241,0.12)'
                                            }}>
                                                <Sparkles className="w-8 h-8" style={{ color: 'var(--accent-secondary)' }} />
                                            </div>

                                            <h3 className="text-lg font-bold mb-2" style={{
                                                fontFamily: "'Plus Jakarta Sans', Inter, sans-serif",
                                                background: 'linear-gradient(135deg, #e0e7ff 0%, #a5b4fc 100%)',
                                                WebkitBackgroundClip: 'text',
                                                WebkitTextFillColor: 'transparent',
                                                backgroundClip: 'text'
                                            }}>
                                                Добро пожаловать
                                            </h3>
                                            <p className="text-sm leading-relaxed mb-7" style={{ color: 'var(--text-tertiary)' }}>
                                                Загрузите документы слева, затем задавайте вопросы через вкладки «Документ» или «Все документы»
                                            </p>

                                            <div className="space-y-2.5">
                                                <div
                                                    className="feature-card"
                                                    style={{ animation: "slideInUp 0.5s cubic-bezier(0.16,1,0.3,1) 100ms both" }}
                                                >
                                                    <div className="feature-icon">
                                                        <Zap className="w-4 h-4" style={{ color: 'var(--accent-secondary)' }} />
                                                    </div>
                                                    <div className="text-left">
                                                        <p className="text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>Умный анализ</p>
                                                        <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Автоматический чанкинг и эмбеддинги</p>
                                                    </div>
                                                </div>
                                                <div
                                                    className="feature-card"
                                                    style={{ animation: "slideInUp 0.5s cubic-bezier(0.16,1,0.3,1) 180ms both" }}
                                                >
                                                    <div className="feature-icon" style={{
                                                        background: 'linear-gradient(135deg, rgba(6,182,212,0.15), rgba(6,182,212,0.05))',
                                                        border: '1px solid rgba(6,182,212,0.20)'
                                                    }}>
                                                        <Globe className="w-4 h-4" style={{ color: 'var(--cyan)' }} />
                                                    </div>
                                                    <div className="text-left">
                                                        <p className="text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>Глобальный поиск</p>
                                                        <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Вопросы по всей базе знаний</p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ) : activeTab === "chat" ? (
                                    <ChatInterface
                                        document={selectedDocument}
                                        isGlobalMode={false}
                                        onNoDocument={() => setActiveTab("upload")}
                                        messages={currentDocChatState?.messages || []}
                                        sessionId={currentDocChatState?.sessionId || null}
                                        onMessagesChange={handleDocMessagesChange}
                                    />
                                ) : (
                                    <ChatInterface
                                        document={null}
                                        isGlobalMode={true}
                                        onNoDocument={() => setActiveTab("upload")}
                                        messages={globalChatState?.messages || []}
                                        sessionId={globalChatState?.sessionId || null}
                                        onMessagesChange={handleGlobalMessagesChange}
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
