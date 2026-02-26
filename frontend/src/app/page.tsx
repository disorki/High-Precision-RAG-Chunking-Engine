"use client";

import { useState, useEffect, MouseEvent } from "react";
import {
    Database, Upload, FileText, Globe, Bot, Plus,
    CheckCircle, Clock, AlertCircle, Trash2, RefreshCw,
    MessageSquare, Sparkles
} from "lucide-react";
import AgentChat from "@/components/AgentChat";
import UploadZone from "@/components/UploadZone";
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

type ChatMode = "document" | "global";

export default function Home() {
    const [documents, setDocuments] = useState<Document[]>([]);
    const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
    const [chatMode, setChatMode] = useState<ChatMode>("global");
    const [showPdf, setShowPdf] = useState(false);
    const [showUpload, setShowUpload] = useState(false);
    const [showSync, setShowSync] = useState(false);

    // Load documents
    useEffect(() => {
        const load = async () => {
            try {
                const r = await fetch("/api/documents");
                if (r.ok) {
                    const data: Document[] = await r.json();
                    setDocuments(data);
                    const ready = data.find(d => d.status === "ready");
                    if (ready) { setSelectedDoc(ready); setChatMode("document"); }
                }
            } catch { }
        };
        load();
    }, []);

    // Poll processing docs
    useEffect(() => {
        const proc = documents.filter(d => d.status === "processing");
        if (!proc.length) return;
        const t = setInterval(async () => {
            for (const doc of proc) {
                try {
                    const r = await fetch(`/api/documents/${doc.id}`);
                    if (r.ok) {
                        const upd: Document = await r.json();
                        setDocuments(prev => prev.map(d => d.id === upd.id ? upd : d));
                        if (selectedDoc?.id === upd.id) setSelectedDoc(upd);
                    }
                } catch { }
            }
        }, 1500);
        return () => clearInterval(t);
    }, [documents, selectedDoc]);

    const handleUploaded = (doc: Document) => {
        setDocuments(prev => [doc, ...prev]);
        setSelectedDoc(doc);
        setShowUpload(false);
    };

    const handleReady = (docId: number) => {
        setDocuments(prev => prev.map(d => d.id === docId ? { ...d, status: "ready" as const } : d));
    };

    const deleteDoc = async (docId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await fetch(`/api/documents/${docId}`, { method: "DELETE" });
            setDocuments(prev => prev.filter(d => d.id !== docId));
            if (selectedDoc?.id === docId) {
                setSelectedDoc(null);
                setChatMode("global");
            }
        } catch { }
    };

    const selectDoc = (doc: Document) => {
        setSelectedDoc(doc);
        setChatMode("document");
    };

    const ready = documents.filter(d => d.status === "ready");

    return (
        <div className="app-shell">
            {/* ═══ SIDEBAR ═══ */}
            <aside className="sidebar">
                {/* Logo */}
                <div className="sidebar-logo">
                    <div className="sidebar-logo-mark">
                        <Database style={{ width: 16, height: 16, color: "#fff" }} />
                    </div>
                    <div className="sidebar-logo-text">
                        <h1>RAG System</h1>
                        <p>Анализ документов с AI</p>
                    </div>
                </div>

                {/* Upload button */}
                <div style={{ padding: "12px 14px 0" }}>
                    <button
                        onClick={() => setShowUpload(v => !v)}
                        style={{
                            width: "100%", display: "flex", alignItems: "center", gap: 8,
                            padding: "9px 12px", borderRadius: 10,
                            border: "1.5px dashed var(--border-md)",
                            background: showUpload ? "var(--accent-dim)" : "transparent",
                            color: showUpload ? "var(--accent)" : "var(--text-3)",
                            cursor: "pointer", fontSize: 13, fontWeight: 500,
                            fontFamily: "inherit", transition: "all .2s",
                        }}
                    >
                        <Upload style={{ width: 15, height: 15 }} />
                        Загрузить документы
                    </button>

                    {showUpload && (
                        <div style={{ marginTop: 10, animation: "fadeUp .2s ease" }}>
                            <UploadZone onDocumentUploaded={handleUploaded} onDocumentReady={handleReady} />
                        </div>
                    )}
                </div>

                {/* Documents list */}
                <div className="sidebar-section" style={{ marginTop: 14 }}>
                    <div className="sidebar-section-header">
                        <span className="sidebar-section-title">Документы</span>
                        <span style={{
                            fontSize: 11, fontWeight: 600,
                            background: "var(--accent-dim)", color: "var(--accent)",
                            padding: "1px 7px", borderRadius: 100,
                        }}>{ready.length}</span>
                    </div>

                    {documents.length === 0 && (
                        <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-3)", fontSize: 12 }}>
                            <FileText style={{ width: 28, height: 28, margin: "0 auto 8px", opacity: .4 }} />
                            <p>Нет документов</p>
                        </div>
                    )}

                    {documents.map(doc => (
                        <div
                            key={doc.id}
                            className={`doc-row ${selectedDoc?.id === doc.id && chatMode === "document" ? "active" : ""}`}
                            onClick={() => selectDoc(doc)}
                        >
                            <div className="doc-icon">
                                <FileText style={{ width: 14, height: 14, color: selectedDoc?.id === doc.id ? "var(--accent)" : "var(--text-3)" }} />
                            </div>
                            <div className="doc-row-info">
                                <div className="doc-row-name" title={doc.original_filename}>
                                    {doc.original_filename}
                                </div>
                                <div className="doc-row-meta">
                                    {doc.status === "ready" && (
                                        <>
                                            <span className="dot dot-ready" />
                                            <span>{doc.page_count} стр.</span>
                                        </>
                                    )}
                                    {doc.status === "processing" && (
                                        <>
                                            <span className="dot dot-proc" />
                                            <span>Обработка…</span>
                                        </>
                                    )}
                                    {doc.status === "failed" && (
                                        <>
                                            <span className="dot dot-error" />
                                            <span>Ошибка</span>
                                        </>
                                    )}
                                </div>
                            </div>
                            <button
                                className="icon-btn"
                                onClick={(e) => deleteDoc(doc.id, e)}
                                style={{ opacity: 0 }}
                                onMouseEnter={e => (e.currentTarget.style.opacity = "1")}
                                onMouseLeave={e => (e.currentTarget.style.opacity = "0")}
                            >
                                <Trash2 style={{ width: 12, height: 12 }} />
                            </button>
                        </div>
                    ))}
                </div>

                {/* Sync at bottom */}
                <div className="sidebar-bottom">
                    <div className="sync-row" onClick={() => setShowSync(v => !v)}>
                        <RefreshCw style={{ width: 14, height: 14 }} />
                        <span>Яндекс.Диск</span>
                        <Plus style={{ width: 12, height: 12, marginLeft: "auto" }} />
                    </div>
                    {showSync && (
                        <div style={{ marginTop: 8, animation: "fadeUp .2s ease" }}>
                            <SyncSourcePanel onDocumentUploaded={handleUploaded} existingDocuments={documents} />
                        </div>
                    )}
                </div>
            </aside>

            {/* ═══ MAIN PANEL ═══ */}
            <main className="main-panel">
                {/* Top bar */}
                <div className="topbar">
                    <button
                        className={`tab-btn ${chatMode === "document" ? "active" : ""}`}
                        onClick={() => { if (selectedDoc) setChatMode("document"); }}
                        disabled={!selectedDoc}
                        style={{ opacity: selectedDoc ? 1 : 0.4 }}
                    >
                        <MessageSquare style={{ width: 14, height: 14 }} />
                        Документ
                    </button>
                    <button
                        className={`tab-btn ${chatMode === "global" ? "active" : ""}`}
                        onClick={() => setChatMode("global")}
                    >
                        <Globe style={{ width: 14, height: 14 }} />
                        Все документы
                    </button>

                    <div className="topbar-right">
                        <div className="status-pill">
                            <span className="dot dot-ready" style={{ width: 6, height: 6 }} />
                            {ready.length} готово
                        </div>
                    </div>
                </div>

                {/* Chat content */}
                <div className="content-area">
                    {chatMode === "document" && !selectedDoc ? (
                        <div className="welcome-screen">
                            <div className="welcome-icon">
                                <Sparkles style={{ width: 28, height: 28, color: "var(--accent)" }} />
                            </div>
                            <h2>Выберите документ</h2>
                            <p>Нажмите на документ в левом меню, чтобы начать диалог с ним</p>
                        </div>
                    ) : chatMode === "document" && selectedDoc ? (
                        <AgentChat
                            document={{ id: selectedDoc.id, name: selectedDoc.original_filename }}
                            sessionKey={String(selectedDoc.id)}
                        />
                    ) : (
                        <AgentChat document={null} sessionKey="global" />
                    )}
                </div>
            </main>

            {/* PDF viewer */}
            {showPdf && selectedDoc && (
                <FileViewer
                    documentId={selectedDoc.id}
                    filename={selectedDoc.original_filename}
                    onClose={() => setShowPdf(false)}
                />
            )}
        </div>
    );
}
