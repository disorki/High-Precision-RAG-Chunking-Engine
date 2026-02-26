"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Bot, Send, Loader2, RotateCcw, AlertCircle, User, FileText, Globe } from "lucide-react";

interface Message {
    id: string;
    role: "user" | "assistant";
    text: string;
    ts: Date;
}

interface DocCtx { id: number; name: string; }

interface Props {
    document?: DocCtx | null;
    sessionKey?: string;
}

function TypingDots() {
    return (
        <div className="typing-dots">
            <span /><span /><span />
        </div>
    );
}

export default function AgentChat({ document, sessionKey }: Props) {
    const isDoc = Boolean(document);
    const configured = Boolean(process.env.NEXT_PUBLIC_FLOWISE_CHATFLOW_ID);
    const sessionId = useRef(`s-${Math.random().toString(36).slice(2, 9)}`);

    const welcomeText = isDoc
        ? `Готов отвечать на вопросы по документу «${document!.name}». Спрашивайте!`
        : "Готов искать по всей базе документов — могу сравнивать, извлекать факты, резюмировать. Спрашивайте!";

    const [msgs, setMsgs] = useState<Message[]>([]);
    const [mounted, setMounted] = useState(false);
    const [input, setInput] = useState("");
    const [thinking, setThinking] = useState(false);
    const [err, setErr] = useState<string | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const textRef = useRef<HTMLTextAreaElement>(null);

    // Reset on context change
    useEffect(() => {
        setMounted(true);
        const welcome: Message = {
            id: `w-${Date.now()}`,
            role: "assistant",
            text: welcomeText,
            ts: new Date()
        };
        sessionId.current = `s-${Math.random().toString(36).slice(2, 9)}`;
        setMsgs([welcome]);
        setErr(null);
        setInput("");
    }, [sessionKey, document?.id, welcomeText]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [msgs, thinking]);

    const send = useCallback(async () => {
        const q = input.trim();
        if (!q || thinking) return;

        const questionSent = isDoc && document
            ? `[Работай ТОЛЬКО с документом ID=${document.id} («${document.name}»)]\n${q}`
            : q;

        setMsgs(p => [...p, { id: crypto.randomUUID(), role: "user", text: q, ts: new Date() }]);
        setInput("");
        setThinking(true);
        setErr(null);

        try {
            const r = await fetch("/api/agent", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: questionSent, sessionId: sessionId.current }),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
            setMsgs(p => [...p, { id: crypto.randomUUID(), role: "assistant", text: d.text || "Нет ответа", ts: new Date() }]);
        } catch (e) {
            setErr(e instanceof Error ? e.message : "Ошибка");
        } finally {
            setThinking(false);
            setTimeout(() => textRef.current?.focus(), 60);
        }
    }, [input, thinking, document, isDoc]);

    const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    };

    const clear = () => {
        sessionId.current = `s-${Math.random().toString(36).slice(2, 9)}`;
        setMsgs([
            {
                id: `w-${Date.now()}`,
                role: "assistant",
                text: welcomeText,
                ts: new Date()
            }
        ]);
        setErr(null);
    };

    if (!configured) {
        return (
            <div className="welcome-screen">
                <div className="welcome-icon">
                    <Bot style={{ width: 28, height: 28, color: "var(--accent)" }} />
                </div>
                <h2>Агент не настроен</h2>
                <p>Добавьте <code>NEXT_PUBLIC_FLOWISE_CHATFLOW_ID</code> в docker-compose.yml</p>
            </div>
        );
    }

    const fmt = (d: Date) => d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });

    return (
        <div className="chat-layout">
            {/* Context bar */}
            <div className="chat-context-bar">
                {isDoc
                    ? <><FileText style={{ width: 13, height: 13 }} /><span>Режим: </span><span className="chat-context-name">{document?.name}</span></>
                    : <><Globe style={{ width: 13, height: 13 }} /><span className="chat-context-name">Все документы</span></>
                }
                <button className="icon-btn" onClick={clear} style={{ marginLeft: "auto" }} title="Новый диалог">
                    <RotateCcw style={{ width: 13, height: 13 }} />
                </button>
            </div>

            {/* Messages */}
            <div className="chat-messages">
                {mounted && msgs.map(msg => (
                    <div key={msg.id} className={`msg-row ${msg.role === "user" ? "user" : "bot"} animate-fade-up`}>
                        <div className={`msg-avatar ${msg.role === "assistant" ? "bot-av" : "user-av"}`}>
                            {msg.role === "assistant"
                                ? <Bot style={{ width: 14, height: 14, color: "var(--green)" }} />
                                : <User style={{ width: 14, height: 14, color: "var(--accent)" }} />
                            }
                        </div>
                        <div>
                            <div className={`msg-bubble ${msg.role === "assistant" ? "bot-b" : "user-b"}`}>
                                {msg.text}
                            </div>
                            <div className="msg-time">{fmt(msg.ts)}</div>
                        </div>
                    </div>
                ))}

                {thinking && (
                    <div className="msg-row bot animate-fade-up">
                        <div className="msg-avatar bot-av">
                            <Bot style={{ width: 14, height: 14, color: "var(--green)" }} />
                        </div>
                        <div>
                            <div className="msg-bubble bot-b">
                                <TypingDots />
                            </div>
                        </div>
                    </div>
                )}

                <div ref={bottomRef} />
            </div>

            {/* Error */}
            {err && (
                <div className="error-bar">
                    <AlertCircle style={{ width: 14, height: 14, flexShrink: 0 }} />
                    {err}
                </div>
            )}

            {/* Input */}
            <div className="chat-input-bar">
                <div className="chat-input-wrap">
                    <textarea
                        ref={textRef}
                        value={input}
                        onChange={e => {
                            setInput(e.target.value);
                            e.target.style.height = "auto";
                            e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
                        }}
                        onKeyDown={onKey}
                        rows={1}
                        disabled={thinking}
                        placeholder={isDoc
                            ? `Вопрос по «${document?.name}»… (Enter — отправить, Shift+Enter — перенос)`
                            : "Вопрос по всем документам…"
                        }
                    />
                    <button
                        className={`send-btn ${input.trim() && !thinking ? "active" : ""}`}
                        onClick={send}
                        disabled={!input.trim() || thinking}
                    >
                        {thinking
                            ? <Loader2 style={{ width: 15, height: 15, color: "var(--accent)", animation: "spin .8s linear infinite" }} />
                            : <Send style={{ width: 14, height: 14, color: input.trim() ? "#fff" : "var(--text-3)" }} />
                        }
                    </button>
                </div>
                <p className="chat-hint">
                    AI Агент · {isDoc ? `поиск в «${document?.name?.slice(0, 30)}${(document?.name?.length ?? 0) > 30 ? "…" : ""}»` : "поиск по всей базе"}
                </p>
            </div>
        </div>
    );
}
