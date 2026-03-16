import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://backend:8000";

export async function POST(req: NextRequest) {
    try {
        const { question, sessionId, documentId } = await req.json();

        if (!question?.trim()) {
            return NextResponse.json({ error: "Empty question" }, { status: 400 });
        }

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
            const text = await response.text();
            console.error("[agent/route] backend error:", response.status, text);
            return NextResponse.json(
                { error: `Backend error: ${response.status}`, detail: text },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json({
            text: data.text || "",
            sources: data.sources || [],
            documents_used: data.documents_used || 0,
        });
    } catch (err) {
        console.error("[agent/route] error:", err);
        return NextResponse.json({ error: "Internal error" }, { status: 500 });
    }
}
