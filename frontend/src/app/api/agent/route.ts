import { NextRequest, NextResponse } from "next/server";

const FLOWISE_HOST = process.env.FLOWISE_INTERNAL_HOST || "http://flowise:3000";
const FLOWISE_CHATFLOW_ID = process.env.NEXT_PUBLIC_FLOWISE_CHATFLOW_ID || "";
const FLOWISE_API_KEY = process.env.FLOWISE_API_KEY || "";

export async function POST(req: NextRequest) {
    try {
        const { question, sessionId } = await req.json();

        if (!question?.trim()) {
            return NextResponse.json({ error: "Empty question" }, { status: 400 });
        }

        if (!FLOWISE_CHATFLOW_ID) {
            return NextResponse.json({ error: "Chatflow not configured" }, { status: 503 });
        }

        const headers: Record<string, string> = {
            "Content-Type": "application/json",
        };
        if (FLOWISE_API_KEY) {
            headers["x-api-key"] = FLOWISE_API_KEY;
        }

        const response = await fetch(
            `${FLOWISE_HOST}/api/v1/prediction/${FLOWISE_CHATFLOW_ID}`,
            {
                method: "POST",
                headers,
                body: JSON.stringify({
                    question,
                    ...(sessionId ? { sessionId } : {}),
                }),
            }
        );

        if (!response.ok) {
            const text = await response.text();
            return NextResponse.json(
                { error: `Flowise error: ${response.status}`, detail: text },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json({ text: data.text || data.answer || "" });
    } catch (err) {
        console.error("[agent/route] error:", err);
        return NextResponse.json({ error: "Internal error" }, { status: 500 });
    }
}
