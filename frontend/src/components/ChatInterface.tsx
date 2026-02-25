"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, AlertCircle, MessageCircle, Sparkles, Globe, Upload as UploadIcon } from "lucide-react";

interface Document {
    id: number;
    filename: string;
    original_filename: string;
    status: "processing" | "ready" | "failed";
}

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
}

interface Source {
    chunk_id: number;
    text: string;
    page_number?: number;
    score: number;
}

interface ChatInterfaceProps {
    document: Document | null;
    isGlobalMode: boolean;
    onNoDocument: () => void;
    messages: Message[];
    sessionId: number | null;
    onMessagesChange: (messages: Message[], sessionId: number | null) => void;
}

export default function ChatInterface({
    document,
    isGlobalMode,
    onNoDocument,
    messages,
    sessionId,
    onMessagesChange,
}: ChatInterfaceProps) {
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [sources, setSources] = useState<Source[]>([]);
    const [currentSessionId, setCurrentSessionId] = useState<number | null>(sessionId);
    const [error, setError] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const lastMessage = messages[messages.length - 1];
    const isWaitingForResponse = lastMessage?.role === "user" ||
        (lastMessage?.role === "assistant" && lastMessage.content === "");

    useEffect(() => {
        setCurrentSessionId(sessionId);
    }, [sessionId]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;
        if (!isGlobalMode && !document) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: input.trim(),
        };

        const updatedMessages = [...messages, userMessage];
        onMessagesChange(updatedMessages, currentSessionId);
        setInput("");
        setIsLoading(true);
        setError(null);

        try {
            const body: Record<string, unknown> = {
                message: userMessage.content,
                session_id: currentSessionId,
            };

            if (!isGlobalMode && document) {
                body.document_id = document.id;
            }

            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Failed to send message");
            }

            const newSessionId = response.headers.get("X-Session-Id");
            let updatedSessionId = currentSessionId;
            if (newSessionId) {
                updatedSessionId = parseInt(newSessionId);
                setCurrentSessionId(updatedSessionId);
            }

            const sourcesHeader = response.headers.get("X-Sources");
            if (sourcesHeader) {
                try {
                    setSources(JSON.parse(sourcesHeader));
                } catch {
                    console.error("Failed to parse sources");
                }
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: "",
            };

            let currentMessages = [...updatedMessages, assistantMessage];
            onMessagesChange(currentMessages, updatedSessionId);

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split("\n");

                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            try {
                                const data = JSON.parse(line.slice(6));

                                if (data.status === "thinking") {
                                    currentMessages = currentMessages.map((msg) =>
                                        msg.id === assistantMessage.id
                                            ? { ...msg, content: "Analyzing documents..." }
                                            : msg
                                    );
                                    onMessagesChange(currentMessages, updatedSessionId);
                                }

                                if (data.content) {
                                    currentMessages = currentMessages.map((msg) =>
                                        msg.id === assistantMessage.id
                                            ? { ...msg, content: msg.content === "Analyzing documents..." ? data.content : msg.content + data.content }
                                            : msg
                                    );
                                    onMessagesChange(currentMessages, updatedSessionId);
                                }
                                if (data.error) {
                                    throw new Error(data.error);
                                }

                                if (data.done && updatedSessionId) {
                                    const finalMessage = currentMessages.find(m => m.id === assistantMessage.id);
                                    if (finalMessage?.content) {
                                        fetch("/api/chat/save-response", {
                                            method: "POST",
                                            headers: { "Content-Type": "application/json" },
                                            body: JSON.stringify({
                                                session_id: updatedSessionId,
                                                content: finalMessage.content
                                            })
                                        }).catch(err => console.error("Failed to save response:", err));
                                    }
                                }
                            } catch (e) {
                                if (e instanceof SyntaxError) continue;
                                throw e;
                            }
                        }
                    }
                }
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Something went wrong");
            const last = messages[messages.length - 1];
            if (last?.role === "assistant" && !last.content) {
                onMessagesChange(messages.slice(0, -1), currentSessionId);
            }
        } finally {
            setIsLoading(false);
        }
    };

    const renderMessages = (placeholder: string) => (
        <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto p-5 space-y-5">
                {messages.length === 0 ? (
                    <div className="empty-state h-full">
                        <div className="empty-state-icon">
                            {isGlobalMode
                                ? <Globe className="w-7 h-7" style={{ color: 'var(--cyan)' }} />
                                : <MessageCircle className="w-7 h-7" style={{ color: 'var(--accent-secondary)' }} />
                            }
                        </div>
                        <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                            {isGlobalMode ? "Глобальная база знаний" : "Чат готов"}
                        </h3>
                        <p className="text-sm max-w-xs leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
                            {isGlobalMode
                                ? "Задавайте вопросы по всем загруженным документам."
                                : `Задавайте вопросы о "${document?.original_filename}" и я отвечу на основе содержимого.`
                            }
                        </p>
                    </div>
                ) : (
                    <>
                        {messages.map((message, idx) => (
                            <div
                                key={message.id}
                                className={`message-container ${message.role === "user" ? "justify-end" : "justify-start"}`}
                                style={{ animationDelay: `${idx * 20}ms` }}
                            >
                                <div className={`max-w-[78%] ${message.role === "user" ? "message-user" : "message-assistant"}`}>
                                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                                        {message.content}
                                    </p>
                                </div>
                            </div>
                        ))}

                        {(isLoading || isWaitingForResponse) && messages[messages.length - 1]?.role !== "assistant" && (
                            <div className="message-container justify-start">
                                <div className="message-assistant">
                                    <div className="typing-indicator">
                                        <span /><span /><span />
                                    </div>
                                </div>
                            </div>
                        )}
                    </>
                )}

                {error && (
                    <div className="flex justify-center">
                        <div className="notification-badge error">
                            <AlertCircle className="w-4 h-4 text-red-400" />
                            <span className="text-sm text-red-400">{error}</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Sources */}
            {sources.length > 0 && (
                <div className="px-5 py-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <p className="text-xs mb-2 flex items-center gap-1" style={{ color: 'var(--text-tertiary)' }}>
                        <Sparkles className="w-3 h-3" style={{ color: 'var(--accent-secondary)' }} />
                        Источники
                    </p>
                    <div className="flex gap-2 overflow-x-auto pb-1">
                        {sources.map((source, i) => (
                            <span key={source.chunk_id} className="source-pill flex-shrink-0">
                                {source.page_number ? `Стр. ${source.page_number}` : `Чанк ${i + 1}`}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Input */}
            <div className="p-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <form onSubmit={handleSubmit} className="flex gap-3">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={placeholder}
                        className="input-premium flex-1"
                        disabled={isLoading}
                        style={{ borderRadius: 14 }}
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        className="btn-premium px-5"
                        style={{ borderRadius: 14, minWidth: 52 }}
                    >
                        {isLoading
                            ? <Loader2 className="w-5 h-5" style={{ animation: 'spin 0.9s linear infinite' }} />
                            : <Send className="w-5 h-5" />
                        }
                    </button>
                </form>
            </div>
        </div>
    );

    // Global mode
    if (isGlobalMode) {
        return renderMessages("Задайте вопрос по всем документам...");
    }

    // No document selected
    if (!document) {
        return (
            <div className="empty-state h-full">
                <div className="empty-state-icon">
                    <AlertCircle className="w-7 h-7" style={{ color: 'var(--text-tertiary)' }} />
                </div>
                <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                    Документ не выбран
                </h3>
                <p className="text-sm mb-6" style={{ color: 'var(--text-tertiary)' }}>
                    Выберите документ чтобы начать
                </p>
                <button onClick={onNoDocument} className="btn-premium">
                    <UploadIcon className="w-4 h-4" />
                    Загрузить документ
                </button>
            </div>
        );
    }

    // Processing
    if (document.status !== "ready") {
        return (
            <div className="empty-state h-full">
                <div className="relative mb-6">
                    <div style={{
                        position: 'absolute', inset: '-8px', borderRadius: '50%',
                        background: 'rgba(99,102,241,0.20)',
                        filter: 'blur(12px)',
                        animation: 'pulseGlow 1.5s ease-in-out infinite'
                    }} />
                    <Loader2 className="relative w-10 h-10" style={{
                        color: 'var(--accent-secondary)',
                        animation: 'spin 0.9s linear infinite'
                    }} />
                </div>
                <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                    Обработка документа
                </h3>
                <p className="text-sm mb-6" style={{ color: 'var(--text-tertiary)' }}>
                    Анализ и индексация документа...
                </p>
                <div className="w-52">
                    <div className="progress-bar">
                        <div className="progress-fill" style={{ width: '66%' }} />
                    </div>
                </div>
            </div>
        );
    }

    return renderMessages("Задайте вопрос по документу...");
}
