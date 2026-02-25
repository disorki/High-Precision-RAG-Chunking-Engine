"use client";

import React, { useState, useEffect } from "react";
import {
    Cloud,
    RefreshCw,
    Plus,
    Trash2,
    FolderSync,
    CheckCircle2,
    AlertCircle,
    Loader2,
    X,
    LogOut,
    HardDrive,
    FolderOpen,
    ExternalLink,
    Link2,
    ArrowRight,
    FileText,
    Download,
    ChevronRight,
    Folder,
    ArrowLeft,
    Check,
} from "lucide-react";

interface SyncSource {
    id: number;
    name: string;
    source_type: string;
    folder_path: string;
    sync_interval: number;
    last_synced_at: string | null;
    status: string;
    error_message: string | null;
    yandex_user: string | null;
    is_connected: boolean;
    oauth_token: string | null;
    created_at: string | null;
}

interface BrowseFolder {
    name: string;
    path: string;
}

interface BrowseFile {
    name: string;
    path: string;
    size: number;
    modified: string;
    extension: string;
}

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

type Step = "idle" | "auth" | "form";

function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "никогда";
    const d = new Date(dateStr);
    const now = new Date();
    const m = Math.floor((now.getTime() - d.getTime()) / 60000);
    if (m < 1) return "только что";
    if (m < 60) return `${m} мин назад`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h} ч назад`;
    const days = Math.floor(h / 24);
    return days === 1 ? "вчера" : `${days} дн назад`;
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

function extIcon(ext: string): string {
    if (ext === ".pdf") return "📕";
    if (ext === ".docx" || ext === ".doc") return "📘";
    if (ext === ".xlsx" || ext === ".xls") return "📗";
    if (ext === ".txt") return "📄";
    return "📎";
}

const INTERVALS = [
    { v: 5, l: "5 мин" },
    { v: 15, l: "15 мин" },
    { v: 30, l: "30 мин" },
    { v: 60, l: "1 час" },
    { v: 360, l: "6 часов" },
    { v: 1440, l: "24 часа" },
];

interface SyncSourcePanelProps {
    onDocumentUploaded?: (doc: Document) => void;
    existingDocuments?: Document[];
}

export default function SyncSourcePanel({ onDocumentUploaded, existingDocuments = [] }: SyncSourcePanelProps) {
    const [sources, setSources] = useState<SyncSource[]>([]);
    const [step, setStep] = useState<Step>("idle");
    const [authUrl, setAuthUrl] = useState("");
    const [apiOk, setApiOk] = useState(true);

    // Auth step
    const [codeInput, setCodeInput] = useState("");
    const [exchanging, setExchanging] = useState(false);
    const [authError, setAuthError] = useState("");

    // Saved after auth
    const [authToken, setAuthToken] = useState("");
    const [authUser, setAuthUser] = useState("");

    // Form step
    const [fName, setFName] = useState("");
    const [fPath, setFPath] = useState("");
    const [fInterval, setFInterval] = useState(30);
    const [creating, setCreating] = useState(false);

    // Source actions
    const [deleteId, setDeleteId] = useState<number | null>(null);
    const [reconnectId, setReconnectId] = useState<number | null>(null);
    const [reconnectCode, setReconnectCode] = useState("");
    const [reconnectExchanging, setReconnectExchanging] = useState(false);
    const [reconnectError, setReconnectError] = useState("");

    // File browser state
    const [browseSourceId, setBrowseSourceId] = useState<number | null>(null);
    const [browsePath, setBrowsePath] = useState("/");
    const [browseFolders, setBrowseFolders] = useState<BrowseFolder[]>([]);
    const [browseFiles, setBrowseFiles] = useState<BrowseFile[]>([]);
    const [browseLoading, setBrowseLoading] = useState(false);
    const [browseError, setBrowseError] = useState("");
    const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
    const [importingFiles, setImportingFiles] = useState<Set<string>>(new Set());

    // Check if a file already exists in the system by original_filename
    const isFileInSystem = (fileName: string): boolean => {
        return existingDocuments.some((d) => d.original_filename === fileName && d.status !== "failed");
    };

    useEffect(() => {
        loadAuthUrl();
        loadSources();
        const t = setInterval(loadSources, 10000);
        return () => clearInterval(t);
    }, []);

    const loadAuthUrl = async () => {
        try {
            const r = await fetch("/api/yandex/auth-url");
            if (r.ok) {
                const d = await r.json();
                setAuthUrl(d.url);
            }
        } catch { }
    };

    const loadSources = async () => {
        try {
            const r = await fetch("/api/sync-sources");
            if (r.ok) {
                setSources(await r.json());
                setApiOk(true);
            } else {
                setApiOk(false);
            }
        } catch {
            setApiOk(false);
        }
    };

    // === AUTH ===
    const startNewConnection = () => {
        setStep("auth");
        setCodeInput("");
        setAuthError("");
        setAuthToken("");
        setAuthUser("");
    };

    const submitCode = async () => {
        if (!codeInput.trim()) return;
        setExchanging(true);
        setAuthError("");
        try {
            const r = await fetch("/api/yandex/exchange-code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: codeInput.trim() }),
            });
            const data = await r.json();
            if (r.ok && data.success) {
                setAuthToken(data.token);
                setAuthUser(data.user || "Яндекс");
                setFName("");
                setFPath("");
                setStep("form");
            } else {
                setAuthError(data.detail || "Неверный код");
            }
        } catch {
            setAuthError("Сервер недоступен");
        }
        setExchanging(false);
    };

    // === CREATE SOURCE ===
    const handleCreate = async () => {
        if (!fName.trim() || !fPath.trim() || !authToken) return;
        setCreating(true);
        try {
            const r = await fetch("/api/sync-sources", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: fName,
                    folder_path: fPath,
                    sync_interval: fInterval,
                    oauth_token: authToken,
                    yandex_user: authUser,
                }),
            });
            if (r.ok) {
                setStep("idle");
                setAuthToken("");
                setAuthUser("");
                loadSources();
            }
        } catch { }
        setCreating(false);
    };

    // === RECONNECT ===
    const submitReconnectCode = async (sourceId: number) => {
        if (!reconnectCode.trim()) return;
        setReconnectExchanging(true);
        setReconnectError("");
        try {
            const r = await fetch("/api/yandex/exchange-code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: reconnectCode.trim(), source_id: sourceId }),
            });
            const data = await r.json();
            if (r.ok && data.success) {
                setReconnectId(null);
                setReconnectCode("");
                loadSources();
            } else {
                setReconnectError(data.detail || "Неверный код");
            }
        } catch {
            setReconnectError("Сервер недоступен");
        }
        setReconnectExchanging(false);
    };

    // === SOURCE ACTIONS ===
    const handleSync = async (id: number) => {
        try {
            await fetch(`/api/sync-sources/${id}/sync`, { method: "POST" });
            setTimeout(loadSources, 500);
        } catch { }
    };

    const handleDisconnect = async (id: number) => {
        try {
            await fetch(`/api/sync-sources/${id}/disconnect`, { method: "POST" });
            loadSources();
        } catch { }
    };

    const handleDelete = async (id: number) => {
        try {
            await fetch(`/api/sync-sources/${id}`, { method: "DELETE" });
            setSources((p) => p.filter((s) => s.id !== id));
            setDeleteId(null);
            if (browseSourceId === id) closeBrowser();
        } catch { }
    };

    const cancelAll = () => {
        setStep("idle");
        setAuthToken("");
        setAuthUser("");
        setAuthError("");
        setCodeInput("");
    };

    // === FILE BROWSER ===
    const openBrowser = async (source: SyncSource) => {
        if (browseSourceId === source.id) {
            closeBrowser();
            return;
        }
        setBrowseSourceId(source.id);
        setBrowsePath("/");
        setSelectedFiles(new Set());
        await loadFolder(source, "/");
    };

    const closeBrowser = () => {
        setBrowseSourceId(null);
        setBrowseFolders([]);
        setBrowseFiles([]);
        setBrowseError("");
        setSelectedFiles(new Set());
    };

    const loadFolder = async (source: SyncSource, path: string) => {
        const token = source.oauth_token || authToken;
        if (!token) return;
        setBrowseLoading(true);
        setBrowseError("");
        setBrowseFolders([]);
        setBrowseFiles([]);
        setSelectedFiles(new Set());

        try {
            const r = await fetch("/api/yandex/browse", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token, path }),
            });
            if (r.ok) {
                const data = await r.json();
                setBrowseFolders(data.folders || []);
                setBrowseFiles(data.files || []);
                setBrowsePath(path);
            } else {
                const err = await r.json();
                setBrowseError(err.detail || "Ошибка загрузки");
            }
        } catch {
            setBrowseError("Не удалось загрузить");
        }
        setBrowseLoading(false);
    };

    const getSourceToken = (sourceId: number): string | null => {
        const source = sources.find((s) => s.id === sourceId);
        return source?.oauth_token || authToken || null;
    };

    const navigateToFolder = (source: SyncSource, folderPath: string) => {
        loadFolder(source, folderPath);
    };

    const navigateUp = (source: SyncSource) => {
        const parts = browsePath.split("/").filter(Boolean);
        parts.pop();
        const parentPath = "/" + parts.join("/");
        loadFolder(source, parentPath || "/");
    };

    const toggleFileSelection = (filePath: string) => {
        setSelectedFiles((prev) => {
            const next = new Set(prev);
            if (next.has(filePath)) {
                next.delete(filePath);
            } else {
                next.add(filePath);
            }
            return next;
        });
    };

    const selectAll = () => {
        const importable = browseFiles.filter((f) => !isFileInSystem(f.name));
        if (selectedFiles.size === importable.length && importable.length > 0) {
            setSelectedFiles(new Set());
        } else {
            setSelectedFiles(new Set(importable.map((f) => f.path)));
        }
    };

    const importSingleFile = async (sourceId: number, file: BrowseFile) => {
        const token = getSourceToken(sourceId);
        if (!token) return;

        setImportingFiles((prev) => new Set(prev).add(file.path));
        try {
            const r = await fetch("/api/yandex/import-file", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    token,
                    file_path: file.path,
                    file_name: file.name,
                }),
            });
            if (r.ok) {
                const data = await r.json();
                if (onDocumentUploaded && data.document_id) {
                    onDocumentUploaded({
                        id: data.document_id,
                        filename: data.filename,
                        original_filename: data.filename,
                        status: "processing",
                        created_at: new Date().toISOString(),
                    });
                }
            }
        } catch { }
        setImportingFiles((prev) => {
            const next = new Set(prev);
            next.delete(file.path);
            return next;
        });
    };

    const importSelected = async (sourceId: number) => {
        const filesToImport = browseFiles.filter((f) => selectedFiles.has(f.path));
        for (const file of filesToImport) {
            await importSingleFile(sourceId, file);
        }
        setSelectedFiles(new Set());
    };

    // Breadcrumbs from path
    const getBreadcrumbs = (path: string) => {
        const parts = path.split("/").filter(Boolean);
        const crumbs = [{ name: "Диск", path: "/" }];
        let current = "";
        for (const part of parts) {
            current += "/" + part;
            crumbs.push({ name: part, path: current });
        }
        return crumbs;
    };

    return (
        <div className="glass-card overflow-hidden animate-in" style={{ animationDelay: "250ms" }}>
            {/* Header */}
            <div className="flex items-center justify-between px-4 pt-4 pb-2">
                <div className="flex items-center gap-2">
                    <div className="sync-header-icon">
                        <Cloud className="w-3.5 h-3.5 text-yellow-400" />
                    </div>
                    <h2 className="text-[13px] font-semibold text-[var(--text-primary)]">
                        Яндекс.Диск
                    </h2>
                </div>
                {step === "idle" ? (
                    <button onClick={startNewConnection} className="sync-header-btn" title="Подключить">
                        <Plus className="w-3.5 h-3.5" />
                    </button>
                ) : (
                    <button onClick={cancelAll} className="sync-header-btn">
                        <X className="w-3.5 h-3.5" />
                    </button>
                )}
            </div>

            <div className="px-4 pb-4 space-y-2">
                {/* DB error */}
                {!apiOk && (
                    <div className="text-[10px] text-amber-400/80 bg-amber-500/5 rounded-lg p-2 flex items-start gap-1.5">
                        <AlertCircle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                        <span>Перезапустите: docker compose down -v && docker compose up --build -d</span>
                    </div>
                )}

                {/* ═══ STEP 1: AUTH ═══ */}
                {step === "auth" && (
                    <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
                        <p className="text-[12px] font-medium text-[var(--text-primary)]">
                            Шаг 1: Авторизация в Яндексе
                        </p>
                        <a
                            href={authUrl || "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="sync-yandex-btn"
                        >
                            <ExternalLink className="w-4 h-4 flex-shrink-0" />
                            <span>Перейти в Яндекс</span>
                            <ArrowRight className="w-3.5 h-3.5 ml-auto flex-shrink-0 opacity-40" />
                        </a>
                        <p className="text-[10px] text-[var(--text-tertiary)] leading-relaxed">
                            Войдите в аккаунт → нажмите «Разрешить» → скопируйте код
                        </p>
                        <div className="flex gap-1.5">
                            <input
                                className="sync-input flex-1 font-mono tracking-wide !text-[13px]"
                                placeholder="Вставьте код"
                                value={codeInput}
                                onChange={(e) => { setCodeInput(e.target.value); setAuthError(""); }}
                                onKeyDown={(e) => e.key === "Enter" && submitCode()}
                            />
                            <button
                                onClick={submitCode}
                                disabled={exchanging || !codeInput.trim()}
                                className="sync-btn-primary !px-3 flex-shrink-0"
                            >
                                {exchanging ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                            </button>
                        </div>
                        {authError && (
                            <p className="text-[10px] text-red-400 flex items-center gap-1">
                                <AlertCircle className="w-3 h-3 flex-shrink-0" /> {authError}
                            </p>
                        )}
                    </div>
                )}

                {/* ═══ STEP 2: FORM ═══ */}
                {step === "form" && (
                    <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-2.5">
                        <div className="flex items-center gap-2 mb-1">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            <p className="text-[12px] font-medium text-emerald-400">
                                {authUser} — подключён
                            </p>
                        </div>
                        <p className="text-[12px] font-medium text-[var(--text-primary)]">
                            Шаг 2: Укажите папку
                        </p>
                        <input className="sync-input" placeholder="Название (напр. Рабочие файлы)" value={fName} onChange={(e) => setFName(e.target.value)} autoFocus />
                        <input className="sync-input" placeholder="Путь (/Документы/RAG)" value={fPath} onChange={(e) => setFPath(e.target.value)} />
                        <select className="sync-input" value={fInterval} onChange={(e) => setFInterval(Number(e.target.value))}>
                            {INTERVALS.map((i) => (
                                <option key={i.v} value={i.v}>каждые {i.l}</option>
                            ))}
                        </select>
                        <button onClick={handleCreate} disabled={creating || !fName.trim() || !fPath.trim()} className="sync-btn-primary w-full">
                            {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Сохранить"}
                        </button>
                    </div>
                )}

                {/* ═══ SOURCE LIST ═══ */}
                {step === "idle" && sources.length === 0 && apiOk && (
                    <div className="text-center py-4">
                        <HardDrive className="w-5 h-5 text-[var(--text-tertiary)] mx-auto mb-2 opacity-40" />
                        <p className="text-[11px] text-[var(--text-tertiary)]">Нет подключений</p>
                        <button onClick={startNewConnection} className="sync-btn-primary mt-3 text-[11px]">
                            <Plus className="w-3 h-3" /> Подключить Диск
                        </button>
                    </div>
                )}

                {step === "idle" && sources.map((s) => (
                    <div key={s.id}>
                        <div className={`sync-card ${s.status === "error" ? "sync-card-error"
                            : s.is_connected ? "sync-card-connected" : "sync-card-disconnected"}`}>
                            <div className="flex items-center gap-2">
                                <div className="sync-card-icon" style={{
                                    background: s.is_connected
                                        ? "linear-gradient(135deg,rgba(34,197,94,.12),rgba(34,197,94,.03))"
                                        : "linear-gradient(135deg,rgba(113,113,122,.12),rgba(113,113,122,.03))",
                                }}>
                                    {s.is_connected
                                        ? <FolderSync className="w-3.5 h-3.5 text-emerald-400" />
                                        : <FolderOpen className="w-3.5 h-3.5 text-zinc-500" />}
                                </div>

                                <div className="flex-1 min-w-0">
                                    <p className="text-[12px] font-medium text-[var(--text-primary)] truncate">{s.name}</p>
                                    <div className="flex items-center gap-2 mt-0.5">
                                        {s.is_connected ? (
                                            <>
                                                <span className="text-[9px] text-emerald-400 flex items-center gap-0.5">
                                                    <CheckCircle2 className="w-2.5 h-2.5" />
                                                    {s.yandex_user || "OK"}
                                                </span>
                                                {s.last_synced_at && (
                                                    <span className="text-[9px] text-[var(--text-tertiary)]">
                                                        {timeAgo(s.last_synced_at)}
                                                    </span>
                                                )}
                                            </>
                                        ) : (
                                            <span className="text-[9px] text-[var(--text-tertiary)]">Не подключён</span>
                                        )}
                                    </div>
                                </div>

                                <div className="flex gap-0.5 flex-shrink-0">
                                    {!s.is_connected && (
                                        <button
                                            onClick={() => {
                                                setReconnectId(reconnectId === s.id ? null : s.id);
                                                setReconnectCode("");
                                                setReconnectError("");
                                            }}
                                            className="sync-action-btn !text-violet-400"
                                            title="Подключить"
                                        >
                                            <Link2 className="w-3.5 h-3.5" />
                                        </button>
                                    )}
                                    {s.is_connected && (
                                        <button
                                            onClick={() => openBrowser(s)}
                                            className={`sync-action-btn ${browseSourceId === s.id ? "!text-cyan-400" : ""}`}
                                            title="Обзор файлов"
                                        >
                                            <Folder className="w-3 h-3" />
                                        </button>
                                    )}
                                    {s.is_connected && (
                                        <button
                                            onClick={() => handleSync(s.id)}
                                            disabled={s.status === "syncing"}
                                            className="sync-action-btn"
                                            title="Синхронизировать"
                                        >
                                            <RefreshCw className={`w-3 h-3 ${s.status === "syncing" ? "animate-spin" : ""}`} />
                                        </button>
                                    )}
                                    {s.is_connected && (
                                        <button onClick={() => handleDisconnect(s.id)} className="sync-action-btn" title="Отключить">
                                            <LogOut className="w-3 h-3" />
                                        </button>
                                    )}
                                    {deleteId === s.id ? (
                                        <div className="flex gap-0.5">
                                            <button onClick={() => handleDelete(s.id)} className="sync-action-btn !text-red-400">
                                                <CheckCircle2 className="w-3 h-3" />
                                            </button>
                                            <button onClick={() => setDeleteId(null)} className="sync-action-btn">
                                                <X className="w-3 h-3" />
                                            </button>
                                        </div>
                                    ) : (
                                        <button onClick={() => setDeleteId(s.id)} className="sync-action-btn sync-action-delete" title="Удалить">
                                            <Trash2 className="w-3 h-3" />
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* Reconnect panel */}
                            {reconnectId === s.id && !s.is_connected && (
                                <div className="mt-2 pt-2 border-t border-[var(--border-subtle)] space-y-2">
                                    <a href={authUrl || "#"} target="_blank" rel="noopener noreferrer" className="sync-yandex-btn">
                                        <ExternalLink className="w-4 h-4 flex-shrink-0" />
                                        <span>Перейти в Яндекс</span>
                                    </a>
                                    <div className="flex gap-1.5">
                                        <input
                                            className="sync-input flex-1 font-mono tracking-wide !text-[13px]"
                                            placeholder="Код из Яндекса"
                                            value={reconnectCode}
                                            onChange={(e) => { setReconnectCode(e.target.value); setReconnectError(""); }}
                                            onKeyDown={(e) => e.key === "Enter" && submitReconnectCode(s.id)}
                                        />
                                        <button
                                            onClick={() => submitReconnectCode(s.id)}
                                            disabled={reconnectExchanging || !reconnectCode.trim()}
                                            className="sync-btn-primary !px-3 flex-shrink-0"
                                        >
                                            {reconnectExchanging ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                                        </button>
                                    </div>
                                    {reconnectError && (
                                        <p className="text-[10px] text-red-400 flex items-center gap-1">
                                            <AlertCircle className="w-3 h-3 flex-shrink-0" /> {reconnectError}
                                        </p>
                                    )}
                                </div>
                            )}

                            {s.error_message && s.status === "error" && (
                                <p className="text-[9px] text-red-400/70 mt-1.5 truncate">{s.error_message}</p>
                            )}
                        </div>

                        {/* ═══ FILE BROWSER ═══ */}
                        {browseSourceId === s.id && s.is_connected && (
                            <div className="mt-1 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] overflow-hidden">
                                {/* Breadcrumb nav */}
                                <div className="flex items-center gap-1 px-3 py-2 border-b border-[var(--border-subtle)] overflow-x-auto">
                                    {browsePath !== "/" && (
                                        <button
                                            onClick={() => navigateUp(s)}
                                            className="p-0.5 rounded hover:bg-white/5 text-[var(--text-tertiary)] flex-shrink-0"
                                        >
                                            <ArrowLeft className="w-3 h-3" />
                                        </button>
                                    )}
                                    {getBreadcrumbs(browsePath).map((crumb, i, arr) => (
                                        <React.Fragment key={crumb.path}>
                                            <button
                                                onClick={() => navigateToFolder(s, crumb.path)}
                                                className={`text-[10px] whitespace-nowrap px-1 py-0.5 rounded hover:bg-white/5
                                                    ${i === arr.length - 1 ? "text-[var(--text-primary)] font-medium" : "text-[var(--text-tertiary)]"}`}
                                            >
                                                {crumb.name}
                                            </button>
                                            {i < arr.length - 1 && (
                                                <ChevronRight className="w-2.5 h-2.5 text-[var(--text-tertiary)] opacity-40 flex-shrink-0" />
                                            )}
                                        </React.Fragment>
                                    ))}
                                </div>

                                {/* Content */}
                                <div className="max-h-[280px] overflow-y-auto">
                                    {browseLoading ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
                                        </div>
                                    ) : browseError ? (
                                        <div className="p-3 text-center">
                                            <p className="text-[10px] text-red-400">{browseError}</p>
                                        </div>
                                    ) : browseFolders.length === 0 && browseFiles.length === 0 ? (
                                        <div className="p-4 text-center">
                                            <p className="text-[10px] text-[var(--text-tertiary)]">Папка пуста</p>
                                        </div>
                                    ) : (
                                        <>
                                            {/* Folders */}
                                            {browseFolders.map((folder) => (
                                                <button
                                                    key={folder.path}
                                                    onClick={() => navigateToFolder(s, folder.path)}
                                                    className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-white/[0.03] transition-colors text-left border-b border-[var(--border-subtle)] last:border-b-0"
                                                >
                                                    <Folder className="w-4 h-4 text-yellow-400/70 flex-shrink-0" />
                                                    <span className="text-[11px] text-[var(--text-primary)] truncate flex-1">{folder.name}</span>
                                                    <ChevronRight className="w-3 h-3 text-[var(--text-tertiary)] opacity-40 flex-shrink-0" />
                                                </button>
                                            ))}

                                            {/* Files */}
                                            {browseFiles.map((file) => {
                                                const inSystem = isFileInSystem(file.name);
                                                return (
                                                    <div
                                                        key={file.path}
                                                        className={`flex items-center gap-2 px-3 py-2 border-b border-[var(--border-subtle)] last:border-b-0 transition-colors
                                                        ${selectedFiles.has(file.path) ? "bg-violet-500/[0.06]" : "hover:bg-white/[0.02]"}
                                                        ${inSystem ? "opacity-50" : ""}`}
                                                    >
                                                        {/* Checkbox */}
                                                        <button
                                                            onClick={() => toggleFileSelection(file.path)}
                                                            disabled={inSystem}
                                                            className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors
                                                            ${selectedFiles.has(file.path)
                                                                    ? "bg-violet-500 border-violet-500"
                                                                    : inSystem
                                                                        ? "border-[var(--border-default)] opacity-30 cursor-not-allowed"
                                                                        : "border-[var(--border-default)] hover:border-violet-400"}`}
                                                        >
                                                            {selectedFiles.has(file.path) && <Check className="w-2.5 h-2.5 text-white" />}
                                                        </button>

                                                        {/* File info */}
                                                        <span className="text-[13px] flex-shrink-0">{extIcon(file.extension)}</span>
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-[11px] text-[var(--text-primary)] truncate">{file.name}</p>
                                                            <p className="text-[9px] text-[var(--text-tertiary)]">
                                                                {inSystem ? "Уже в системе" : formatSize(file.size)}
                                                            </p>
                                                        </div>

                                                        {/* Import button */}
                                                        {inSystem ? (
                                                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400/50 flex-shrink-0" />
                                                        ) : importingFiles.has(file.path) ? (
                                                            <Loader2 className="w-3.5 h-3.5 text-violet-400 animate-spin flex-shrink-0" />
                                                        ) : (
                                                            <button
                                                                onClick={() => importSingleFile(s.id, file)}
                                                                className="p-1 rounded hover:bg-violet-500/10 text-[var(--text-tertiary)] hover:text-violet-400 transition-colors flex-shrink-0"
                                                                title="Импортировать"
                                                            >
                                                                <Download className="w-3.5 h-3.5" />
                                                            </button>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </>
                                    )}
                                </div>

                                {/* Footer: select all + import selected */}
                                {browseFiles.length > 0 && !browseLoading && (
                                    <div className="flex items-center justify-between px-3 py-2 border-t border-[var(--border-subtle)]">
                                        <button
                                            onClick={selectAll}
                                            className="text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
                                        >
                                            {(() => {
                                                const importable = browseFiles.filter((f) => !isFileInSystem(f.name));
                                                return selectedFiles.size === importable.length && importable.length > 0
                                                    ? "Снять всё"
                                                    : `Выбрать все (${importable.length})`;
                                            })()}
                                        </button>
                                        {selectedFiles.size > 0 && (
                                            <button
                                                onClick={() => importSelected(s.id)}
                                                className="sync-btn-primary !text-[10px] !py-1 !px-2.5"
                                            >
                                                <Download className="w-3 h-3" />
                                                Импорт ({selectedFiles.size})
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
