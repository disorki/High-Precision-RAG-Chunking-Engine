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
    Download,
    ChevronRight,
    Folder,
    ArrowLeft,
    Check,
} from "lucide-react";

// (Keep all the interfaces and logic exactly the same)
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

interface BrowseFolder { name: string; path: string; }
interface BrowseFile { name: string; path: string; size: number; modified: string; extension: string; }
interface Document {
    id: number; filename: string; original_filename: string;
    status: "processing" | "ready" | "failed"; error_message?: string;
}
type Step = "idle" | "auth" | "form";

function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "никогда";
    const d = new Date(dateStr); const now = new Date();
    const m = Math.floor((now.getTime() - d.getTime()) / 60000);
    if (m < 1) return "только что"; if (m < 60) return `${m} мин назад`;
    const h = Math.floor(m / 60); if (h < 24) return `${h} ч назад`;
    const days = Math.floor(h / 24); return days === 1 ? "вчера" : `${days} дн назад`;
}
function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}
function extIcon(ext: string): string {
    if (ext === ".pdf") return "📕"; if (ext === ".docx" || ext === ".doc") return "📘";
    if (ext === ".xlsx" || ext === ".xls") return "📗"; if (ext === ".txt") return "📄";
    return "📎";
}
const INTERVALS = [
    { v: 5, l: "5 мин" }, { v: 15, l: "15 мин" }, { v: 30, l: "30 мин" },
    { v: 60, l: "1 час" }, { v: 360, l: "6 часов" }, { v: 1440, l: "24 часа" },
];

export default function SyncSourcePanel({ onDocumentUploaded, existingDocuments = [] }: any) {
    const [sources, setSources] = useState<SyncSource[]>([]);
    const [step, setStep] = useState<Step>("idle");
    const [authUrl, setAuthUrl] = useState("");
    const [apiOk, setApiOk] = useState(true);

    const [codeInput, setCodeInput] = useState("");
    const [exchanging, setExchanging] = useState(false);
    const [authError, setAuthError] = useState("");
    const [authToken, setAuthToken] = useState("");
    const [authUser, setAuthUser] = useState("");

    const [fName, setFName] = useState("");
    const [fPath, setFPath] = useState("");
    const [fInterval, setFInterval] = useState(30);
    const [creating, setCreating] = useState(false);

    const [deleteId, setDeleteId] = useState<number | null>(null);
    const [reconnectId, setReconnectId] = useState<number | null>(null);
    const [reconnectCode, setReconnectCode] = useState("");
    const [reconnectExchanging, setReconnectExchanging] = useState(false);
    const [reconnectError, setReconnectError] = useState("");

    const [browseSourceId, setBrowseSourceId] = useState<number | null>(null);
    const [browsePath, setBrowsePath] = useState("/");
    const [browseFolders, setBrowseFolders] = useState<BrowseFolder[]>([]);
    const [browseFiles, setBrowseFiles] = useState<BrowseFile[]>([]);
    const [browseLoading, setBrowseLoading] = useState(false);
    const [browseError, setBrowseError] = useState("");
    const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
    const [importingFiles, setImportingFiles] = useState<Set<string>>(new Set());

    const isFileInSystem = (fileName: string): boolean => existingDocuments.some((d: any) => d.original_filename === fileName && d.status !== "failed");

    useEffect(() => { loadAuthUrl(); loadSources(); const t = setInterval(loadSources, 10000); return () => clearInterval(t); }, []);

    const loadAuthUrl = async () => { try { const r = await fetch("/api/yandex/auth-url"); if (r.ok) setAuthUrl((await r.json()).url); } catch { } };
    const loadSources = async () => {
        try { const r = await fetch("/api/sync-sources"); if (r.ok) { setSources(await r.json()); setApiOk(true); } else setApiOk(false); } catch { setApiOk(false); }
    };

    const startNewConnection = () => { setStep("auth"); setCodeInput(""); setAuthError(""); setAuthToken(""); setAuthUser(""); };
    const submitCode = async () => {
        if (!codeInput.trim()) return; setExchanging(true); setAuthError("");
        try {
            const r = await fetch("/api/yandex/exchange-code", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: codeInput.trim() }) });
            const data = await r.json();
            if (r.ok && data.success) { setAuthToken(data.token); setAuthUser(data.user || "Яндекс"); setFName(""); setFPath(""); setStep("form"); }
            else setAuthError(data.detail || "Неверный код");
        } catch { setAuthError("Сервер недоступен"); }
        setExchanging(false);
    };

    const handleCreate = async () => {
        if (!fName.trim() || !fPath.trim() || !authToken) return; setCreating(true);
        try {
            const r = await fetch("/api/sync-sources", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: fName, folder_path: fPath, sync_interval: fInterval, oauth_token: authToken, yandex_user: authUser }) });
            if (r.ok) { setStep("idle"); setAuthToken(""); setAuthUser(""); loadSources(); }
        } catch { } setCreating(false);
    };

    const submitReconnectCode = async (sourceId: number) => {
        if (!reconnectCode.trim()) return; setReconnectExchanging(true); setReconnectError("");
        try {
            const r = await fetch("/api/yandex/exchange-code", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: reconnectCode.trim(), source_id: sourceId }) });
            const data = await r.json();
            if (r.ok && data.success) { setReconnectId(null); setReconnectCode(""); loadSources(); }
            else setReconnectError(data.detail || "Неверный код");
        } catch { setReconnectError("Сервер недоступен"); }
        setReconnectExchanging(false);
    };

    const handleSync = async (id: number) => { try { await fetch(`/api/sync-sources/${id}/sync`, { method: "POST" }); setTimeout(loadSources, 500); } catch { } };
    const handleDisconnect = async (id: number) => { try { await fetch(`/api/sync-sources/${id}/disconnect`, { method: "POST" }); loadSources(); } catch { } };
    const handleDelete = async (id: number) => { try { await fetch(`/api/sync-sources/${id}`, { method: "DELETE" }); setSources((p) => p.filter((s) => s.id !== id)); setDeleteId(null); if (browseSourceId === id) closeBrowser(); } catch { } };
    const cancelAll = () => { setStep("idle"); setAuthToken(""); setAuthUser(""); setAuthError(""); setCodeInput(""); };

    const openBrowser = async (source: SyncSource) => {
        if (browseSourceId === source.id) { closeBrowser(); return; }
        setBrowseSourceId(source.id); setBrowsePath("/"); setSelectedFiles(new Set()); await loadFolder(source, "/");
    };
    const closeBrowser = () => { setBrowseSourceId(null); setBrowseFolders([]); setBrowseFiles([]); setBrowseError(""); setSelectedFiles(new Set()); };

    const loadFolder = async (source: SyncSource, path: string) => {
        const token = source.oauth_token || authToken; if (!token) return;
        setBrowseLoading(true); setBrowseError(""); setBrowseFolders([]); setBrowseFiles([]); setSelectedFiles(new Set());
        try {
            const r = await fetch("/api/yandex/browse", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, path }) });
            if (r.ok) { const data = await r.json(); setBrowseFolders(data.folders || []); setBrowseFiles(data.files || []); setBrowsePath(path); }
            else { setBrowseError((await r.json()).detail || "Ошибка загрузки"); }
        } catch { setBrowseError("Не удалось загрузить"); }
        setBrowseLoading(false);
    };

    const getSourceToken = (sourceId: number): string | null => sources.find((s) => s.id === sourceId)?.oauth_token || authToken || null;
    const navigateToFolder = (source: SyncSource, folderPath: string) => { loadFolder(source, folderPath); };
    const navigateUp = (source: SyncSource) => { const parts = browsePath.split("/").filter(Boolean); parts.pop(); loadFolder(source, "/" + parts.join("/")); };

    const toggleFileSelection = (filePath: string) => setSelectedFiles(p => { const n = new Set(p); n.has(filePath) ? n.delete(filePath) : n.add(filePath); return n; });
    const selectAll = () => { const i = browseFiles.filter(f => !isFileInSystem(f.name)); selectedFiles.size === i.length && i.length > 0 ? setSelectedFiles(new Set()) : setSelectedFiles(new Set(i.map(f => f.path))); };

    const importSingleFile = async (sourceId: number, file: BrowseFile) => {
        const token = getSourceToken(sourceId); if (!token) return;
        setImportingFiles(p => new Set(p).add(file.path));
        try {
            const r = await fetch("/api/yandex/import-file", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, file_path: file.path, file_name: file.name }) });
            if (r.ok) {
                const data = await r.json();
                if (onDocumentUploaded && data.document_id) onDocumentUploaded({ id: data.document_id, filename: data.filename, original_filename: data.filename, status: "processing", created_at: new Date().toISOString() });
            }
        } catch { }
        setImportingFiles(p => { const n = new Set(p); n.delete(file.path); return n; });
    };
    const importSelected = async (sourceId: number) => { const files = browseFiles.filter(f => selectedFiles.has(f.path)); for (const file of files) await importSingleFile(sourceId, file); setSelectedFiles(new Set()); };
    const getBreadcrumbs = (path: string) => { const parts = path.split("/").filter(Boolean); const crumbs = [{ name: "Диск", path: "/" }]; let current = ""; for (const part of parts) { current += "/" + part; crumbs.push({ name: part, path: current }); } return crumbs; };

    return (
        <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: "1px solid var(--border)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Cloud style={{ width: 15, height: 15, color: "var(--amber)" }} />
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Яндекс.Диск</span>
                </div>
                {step === "idle" ? (
                    <button onClick={startNewConnection} className="icon-btn"><Plus style={{ width: 14, height: 14 }} /></button>
                ) : (
                    <button onClick={cancelAll} className="icon-btn"><X style={{ width: 14, height: 14 }} /></button>
                )}
            </div>

            <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                {!apiOk && (
                    <div style={{ padding: 8, background: "var(--red-dim)", color: "var(--red)", borderRadius: 8, fontSize: 10, display: "flex", gap: 6 }}>
                        <AlertCircle style={{ width: 12, height: 12 }} /> Ошибка API Яндекса
                    </div>
                )}

                {/* AUTH STEP */}
                {step === "auth" && (
                    <div style={{ padding: 12, background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 10 }}>
                        <p style={{ fontSize: 12, fontWeight: 500, marginBottom: 10 }}>Подключение Яндекс.Диска</p>
                        <a href={authUrl || "#"} target="_blank" rel="noopener noreferrer" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--accent)" }}>
                            Получить код <ExternalLink style={{ width: 12, height: 12 }} />
                        </a>
                        <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                            <input
                                value={codeInput} onChange={(e) => { setCodeInput(e.target.value); setAuthError(""); }} onKeyDown={e => e.key === "Enter" && submitCode()}
                                placeholder="Вставьте код"
                                style={{ flex: 1, padding: "6px 10px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-1)", outline: "none", fontSize: 12 }}
                            />
                            <button onClick={submitCode} disabled={exchanging || !codeInput.trim()}
                                style={{ padding: "6px 12px", background: "var(--accent-dim)", color: "var(--accent)", border: "none", borderRadius: 6, cursor: "pointer" }}>
                                {exchanging ? <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} /> : <ArrowRight style={{ width: 14, height: 14 }} />}
                            </button>
                        </div>
                        {authError && <p style={{ fontSize: 10, color: "var(--red)", marginTop: 6 }}>{authError}</p>}
                    </div>
                )}

                {/* FORM STEP */}
                {step === "form" && (
                    <div style={{ padding: 12, background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--green)", fontSize: 11 }}><CheckCircle2 style={{ width: 12, height: 12 }} /> {authUser}</div>
                        <p style={{ fontSize: 12, fontWeight: 500 }}>Настройка синхронизации</p>
                        <input value={fName} onChange={(e) => setFName(e.target.value)} placeholder="Название (Рабочие файлы)" style={{ padding: "6px 10px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-1)", outline: "none", fontSize: 12 }} />
                        <input value={fPath} onChange={(e) => setFPath(e.target.value)} placeholder="Путь (/Docs)" style={{ padding: "6px 10px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-1)", outline: "none", fontSize: 12 }} />
                        <select value={fInterval} onChange={(e) => setFInterval(Number(e.target.value))} style={{ padding: "6px 10px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-1)", outline: "none", fontSize: 12 }}>
                            {INTERVALS.map(i => <option key={i.v} value={i.v}>каждые {i.l}</option>)}
                        </select>
                        <button onClick={handleCreate} disabled={creating || !fName.trim() || !fPath.trim()}
                            style={{ padding: "6px 12px", background: "var(--accent)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>
                            {creating ? <Loader2 className="animate-spin" style={{ width: 14, height: 14, margin: "0 auto" }} /> : "Сохранить"}
                        </button>
                    </div>
                )}

                {/* LIST */}
                {step === "idle" && sources.length === 0 && apiOk && (
                    <div style={{ textAlign: "center", padding: "20px 0" }}>
                        <p style={{ fontSize: 11, color: "var(--text-3)" }}>Нет подключений</p>
                    </div>
                )}

                {step === "idle" && sources.map((s) => (
                    <div key={s.id} style={{ background: "var(--bg-surface)", borderRadius: 10, padding: 10, border: `1px solid ${s.is_connected ? "rgba(52,211,153,0.2)" : "var(--border)"}` }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <p style={{ fontSize: 12, fontWeight: 500, color: "var(--text-1)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.name}</p>
                                <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                                    {s.is_connected ? (
                                        <>
                                            <span style={{ fontSize: 9, color: "var(--green)" }}>{s.yandex_user || "OK"}</span>
                                            <span style={{ fontSize: 9, color: "var(--text-3)" }}>{timeAgo(s.last_synced_at)}</span>
                                        </>
                                    ) : (
                                        <span style={{ fontSize: 9, color: "var(--text-3)" }}>Не подключён</span>
                                    )}
                                </div>
                            </div>
                            <div style={{ display: "flex", gap: 2 }}>
                                {s.is_connected ? (
                                    <>
                                        <button onClick={() => openBrowser(s)} className="icon-btn"><Folder style={{ width: 13, height: 13, color: browseSourceId === s.id ? "var(--accent)" : "" }} /></button>
                                        <button onClick={() => handleSync(s.id)} className="icon-btn" disabled={s.status === "syncing"}><RefreshCw style={{ width: 13, height: 13 }} className={s.status === "syncing" ? "animate-spin" : ""} /></button>
                                        <button onClick={() => handleDisconnect(s.id)} className="icon-btn"><LogOut style={{ width: 13, height: 13 }} /></button>
                                    </>
                                ) : (
                                    <button onClick={() => { setReconnectId(reconnectId === s.id ? null : s.id); setReconnectCode(""); }} className="icon-btn"><Link2 style={{ width: 13, height: 13, color: "var(--accent)" }} /></button>
                                )}
                                {deleteId === s.id ? (
                                    <>
                                        <button onClick={() => handleDelete(s.id)} className="icon-btn"><CheckCircle2 style={{ width: 13, height: 13, color: "var(--red)" }} /></button>
                                        <button onClick={() => setDeleteId(null)} className="icon-btn"><X style={{ width: 13, height: 13 }} /></button>
                                    </>
                                ) : (
                                    <button onClick={() => setDeleteId(s.id)} className="icon-btn"><Trash2 style={{ width: 13, height: 13 }} /></button>
                                )}
                            </div>
                        </div>

                        {/* RECONNECT PANEL */}
                        {reconnectId === s.id && !s.is_connected && (
                            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 8 }}>
                                <a href={authUrl || "#"} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: "var(--accent)" }}>Войти в Яндекс</a>
                                <div style={{ display: "flex", gap: 6 }}>
                                    <input value={reconnectCode} onChange={e => setReconnectCode(e.target.value)} placeholder="Код" style={{ flex: 1, padding: "4px 8px", fontSize: 11, background: "var(--bg-card)", border: "none", borderRadius: 4, color: "var(--text-1)", outline: "none" }} />
                                    <button onClick={() => submitReconnectCode(s.id)} disabled={reconnectExchanging || !reconnectCode.trim()} style={{ background: "var(--accent-dim)", padding: "4px 8px", borderRadius: 4, color: "var(--accent)", border: "none", cursor: "pointer" }}>
                                        {reconnectExchanging ? <Loader2 style={{ width: 12, height: 12 }} className="animate-spin" /> : <CheckCircle2 style={{ width: 12, height: 12 }} />}
                                    </button>
                                </div>
                                {reconnectError && <p style={{ fontSize: 10, color: "var(--red)" }}>{reconnectError}</p>}
                            </div>
                        )}

                        {/* BROWSER */}
                        {browseSourceId === s.id && s.is_connected && (
                            <div style={{ marginTop: 8, border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
                                {/* Breadcrumbs */}
                                <div style={{ padding: "6px 8px", background: "var(--bg-card)", display: "flex", gap: 4, borderBottom: "1px solid var(--border)", fontSize: 10, overflowX: "auto" }}>
                                    {browsePath !== "/" && <button onClick={() => navigateUp(s)} style={{ border: "none", background: "none", color: "var(--text-3)", cursor: "pointer" }}><ArrowLeft style={{ width: 10, height: 10 }} /></button>}
                                    {getBreadcrumbs(browsePath).map((c, i, arr) => (
                                        <React.Fragment key={c.path}>
                                            <button onClick={() => navigateToFolder(s, c.path)} style={{ border: "none", background: "none", cursor: "pointer", color: i === arr.length - 1 ? "var(--text-1)" : "var(--text-3)", whiteSpace: "nowrap" }}>{c.name}</button>
                                            {i < arr.length - 1 && <span style={{ color: "var(--text-3)" }}>/</span>}
                                        </React.Fragment>
                                    ))}
                                </div>
                                {/* Explorer */}
                                <div style={{ maxHeight: 200, overflowY: "auto" }}>
                                    {browseLoading ? <div style={{ padding: 20, textAlign: "center" }}><Loader2 className="animate-spin mx-auto" style={{ width: 16, height: 16, color: "var(--accent)" }} /></div>
                                        : (
                                            <>
                                                {browseFolders.map(f => (
                                                    <div key={f.path} onClick={() => navigateToFolder(s, f.path)} style={{ padding: "8px 10px", display: "flex", alignItems: "center", gap: 8, cursor: "pointer", borderBottom: "1px solid var(--border)", fontSize: 11 }}>
                                                        <Folder style={{ width: 14, height: 14, color: "var(--amber)" }} />
                                                        <span style={{ flex: 1 }}>{f.name}</span>
                                                    </div>
                                                ))}
                                                {browseFiles.map(f => {
                                                    const inSys = isFileInSystem(f.name);
                                                    return (
                                                        <div key={f.path} style={{ padding: "6px 10px", display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid var(--border)", background: selectedFiles.has(f.path) ? "var(--accent-dim)" : "", opacity: inSys ? 0.5 : 1 }}>
                                                            <input type="checkbox" checked={selectedFiles.has(f.path)} disabled={inSys} onChange={() => toggleFileSelection(f.path)} style={{ cursor: inSys ? "default" : "pointer" }} />
                                                            <span style={{ fontSize: 12 }}>{extIcon(f.extension)}</span>
                                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                                <p style={{ fontSize: 10, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: "var(--text-1)" }}>{f.name}</p>
                                                                <p style={{ fontSize: 9, color: "var(--text-3)" }}>{formatSize(f.size)}</p>
                                                            </div>
                                                            {inSys ? <CheckCircle2 style={{ width: 12, height: 12, color: "var(--green)" }} /> : importingFiles.has(f.path) ? <Loader2 style={{ width: 12, height: 12, color: "var(--accent)" }} className="animate-spin" /> : <button onClick={() => importSingleFile(s.id, f)} className="icon-btn"><Download style={{ width: 12, height: 12 }} /></button>}
                                                        </div>
                                                    )
                                                })}
                                            </>
                                        )}
                                </div>
                                {/* Footer */}
                                {browseFiles.length > 0 && !browseLoading && (
                                    <div style={{ padding: "6px 10px", borderTop: "1px solid var(--border)", background: "var(--bg-card)", display: "flex", justifyContent: "space-between" }}>
                                        <button onClick={selectAll} style={{ background: "none", border: "none", fontSize: 10, color: "var(--text-3)", cursor: "pointer" }}>Выбрать все</button>
                                        {selectedFiles.size > 0 && <button onClick={() => importSelected(s.id)} style={{ padding: "4px 8px", fontSize: 10, background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>Импорт</button>}
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
