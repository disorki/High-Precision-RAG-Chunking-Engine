"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, AlertCircle, MessageCircle, Sparkles } from "lucide-react";

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
    onNoDocument: () => void;
    messages: Message[];
    sessionId: number | null;
    onMessagesChange: (messages: Message[], sessionId: number | null) => void;
}

export default function ChatInterface({
    document,
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

    // Check if we're waiting for a response (last message is from user with empty or no assistant reply)
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
        if (!input.trim() || isLoading || !document) return;

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
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMessage.content,
                    document_id: document.id,
                    session_id: currentSessionId,
                }),
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
                                if (data.content) {
                                    currentMessages = currentMessages.map((msg) =>
                                        msg.id === assistantMessage.id
                                            ? { ...msg, content: data.clear ? data.content : msg.content + data.content }
                                            : msg
                                    );
                                    onMessagesChange(currentMessages, updatedSessionId);
                                }
                                if (data.error) {
                                    throw new Error(data.error);
                                }

                                // Save response when done
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

    if (!document) {
        return (
            <div className="empty-state h-full">
                <div className="empty-state-icon">
                    <AlertCircle className="w-10 h-10 text-[var(--text-tertiary)]" />
                </div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    No Document Selected
                </h3>
                <p className="text-[var(--text-tertiary)] mb-6 max-w-sm">
                    Please select a document to start chatting
                </p>
                <button onClick={onNoDocument} className="btn-premium">
                    <Upload className="w-4 h-4" />
                    Upload a Document
                </button>
            </div>
        );
    }

    if (document.status !== "ready") {
        return (
            <div className="empty-state h-full">
                <div className="relative mb-6">
                    <div className="absolute inset-0 bg-violet-500 rounded-full blur-xl opacity-30 animate-pulse"></div>
                    <Loader2 className="relative w-12 h-12 text-violet-400 animate-spin" />
                </div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    Processing Document
                </h3>
                <p className="text-[var(--text-tertiary)] mb-6">
                    Analyzing and indexing your document...
                </p>
                <div className="w-48">
                    <div className="progress-bar">
                        <div className="progress-fill" style={{ width: '66%' }}></div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.length === 0 ? (
                    <div className="empty-state h-full">
                        <div className="empty-state-icon">
                            <MessageCircle className="w-10 h-10 text-violet-400" />
                        </div>
                        <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                            Ready to Chat
                        </h3>
                        <p className="text-[var(--text-tertiary)] text-sm max-w-sm leading-relaxed">
                            Ask questions about &quot;{document.original_filename}&quot; and I&apos;ll answer based on its content.
                        </p>
                    </div>
                ) : (
                    <>
                        {messages.map((message) => (
                            <div
                                key={message.id}
                                className={`message-container ${message.role === "user" ? "justify-end" : "justify-start"}`}
                            >
                                <div className={`max-w-[75%] ${message.role === "user" ? "message-user" : "message-assistant"}`}>
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
                                        <span></span>
                                        <span></span>
                                        <span></span>
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
                <div className="px-6 py-3 border-t border-[var(--border-subtle)]">
                    <p className="text-xs text-[var(--text-tertiary)] mb-2 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        Sources
                    </p>
                    <div className="flex gap-2 overflow-x-auto pb-1">
                        {sources.map((source, i) => (
                            <span key={source.chunk_id} className="source-pill">
                                {source.page_number ? `Page ${source.page_number}` : `Chunk ${i + 1}`}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Input */}
            <div className="p-4 border-t border-[var(--border-subtle)]">
                <form onSubmit={handleSubmit} className="flex gap-3">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a question about your document..."
                        className="input-premium flex-1"
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        className="btn-premium px-5"
                    >
                        {isLoading ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            <Send className="w-5 h-5" />
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
}

function Upload({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
    );
}
