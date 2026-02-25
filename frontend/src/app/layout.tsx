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
        <html lang="ru">
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                <link
                    href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body className="min-h-screen">
                {children}
            </body>
        </html>
    );
}
