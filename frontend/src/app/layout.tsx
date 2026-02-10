import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "Intelligent RAG System",
    description: "AI-powered Knowledge Base with PDF upload and chat",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className="min-h-screen bg-gradient-to-br from-dark-900 via-dark-800 to-dark-900">
                {children}
            </body>
        </html>
    );
}
