import { NextResponse } from 'next/server';

const API_URL = process.env.API_URL || "http://backend:8000";

export async function POST(req: Request) {
    try {
        const body = await req.json();
        const { question, sessionId, documentId } = body;

        if (!question?.trim()) {
            return NextResponse.json({ error: "Empty question" }, { status: 400 });
        }

        // Вызываем backend напрямую (прямой RAG без Flowise)
        const response = await fetch(`${API_URL}/api/agent/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question.trim(),
                document_id: documentId ?? null,
                session_id: sessionId ?? null,
            }),
        });

        if (!response.ok) {
            const err = await response.text();
            console.error("[agent-endpoint] backend error:", response.status, err);
            return NextResponse.json(
                { error: `Backend error: ${response.status}`, detail: err },
                { status: response.status }
            );
        }

        const data = await response.json();

        return NextResponse.json({
            text: data.text || "Нет ответа",
            sources: data.sources || [],
            documents_used: data.documents_used || 0,
        });

    } catch (e: any) {
        console.error("[agent-endpoint] error:", e);
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
