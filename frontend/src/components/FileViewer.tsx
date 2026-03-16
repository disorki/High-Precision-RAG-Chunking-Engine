"use client";

import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X, Download, Loader2, AlertCircle, FileText, FileSpreadsheet } from "lucide-react";

// Библиотеки будут импортированы динамически в момент использования
interface FileViewerProps {
    documentId: number;
    filename: string;
    onClose: () => void;
}

export default function FileViewer({ documentId, filename, onClose }: FileViewerProps) {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [excelData, setExcelData] = useState<{ name: string, data: any[][] }[]>([]);
    const [activeSheet, setActiveSheet] = useState(0);
    const [mounted, setMounted] = useState(false);
    
    const wordContainerRef = useRef<HTMLDivElement>(null);
    const fileUrl = `/api/documents/${documentId}/file`;
    const ext = filename.toLowerCase().split(".").pop() || "";
    
    const isPdf = ext === "pdf";
    const isTxt = ext === "txt";
    const isWord = ["docx", "doc"].includes(ext);
    const isExcel = ["xlsx", "xls", "csv"].includes(ext);

    useEffect(() => {
        setMounted(true);
        const handleEsc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
        window.addEventListener("keydown", handleEsc);
        
        if (isWord || isExcel) {
            loadFile();
        } else {
            setIsLoading(false);
        }

        return () => window.removeEventListener("keydown", handleEsc);
    }, []);

    const loadFile = async () => {
        try {
            setIsLoading(true);
            const response = await fetch(fileUrl);
            if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
            const arrayBuffer = await response.arrayBuffer();

            if (isWord) {
                // Стандартный динамический импорт. Теперь, когда вы установили библиотеку в докер,
                // Next.js сможет найти её и собрать бандл.
                let docxModule;
                try {
                    docxModule = await import("docx-preview");
                } catch (e) {
                    throw new Error("Библиотека 'docx-preview' не найдена. Если вы только что её установили, попробуйте перезагрузить Docker контейнер.");
                }

                setTimeout(async () => {
                    if (wordContainerRef.current) {
                        try {
                            wordContainerRef.current.innerHTML = "";
                            await docxModule.renderAsync(arrayBuffer, wordContainerRef.current, undefined, {
                                inWrapper: false,
                                ignoreWidth: false,
                                ignoreHeight: false,
                            });
                        } catch (err) {
                            setError("Ошибка отрисовки Word-файла");
                        } finally {
                            setIsLoading(false);
                        }
                    }
                }, 200);
            } else if (isExcel) {
                // Стандартный динамический импорт
                let XLSXModule;
                try {
                    XLSXModule = await import("xlsx");
                } catch (e) {
                    throw new Error("Библиотека 'xlsx' не найдена. Если вы только что её установили, попробуйте перезагрузить Docker контейнер.");
                }

                try {
                    const workbook = XLSXModule.read(arrayBuffer, { type: 'array' });
                    const sheets = workbook.SheetNames.map((name: string) => ({
                        name,
                        data: XLSXModule.utils.sheet_to_json(workbook.Sheets[name], { header: 1 }) as any[][]
                    }));
                    setExcelData(sheets);
                    setIsLoading(false);
                } catch (err) {
                    setError("Ошибка парсинга Excel");
                    setIsLoading(false);
                }
            }
        } catch (err: any) {
            setError(err.message || "Ошибка загрузки");
            setIsLoading(false);
        }
    };

    if (!mounted) return null;

    const modal = (
        <div style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            zIndex: 999999,
            backgroundColor: 'rgba(0,0,0,0.95)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            fontFamily: 'sans-serif'
        }}>
            <div style={{
                position: 'relative',
                width: '100vw',
                maxWidth: '1300px',
                height: '92vh',
                backgroundColor: '#0a0a0f',
                borderRadius: '20px',
                border: '1px solid #333',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                color: '#fff',
                boxShadow: '0 0 50px rgba(0,0,0,0.5)'
            }}>
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 25px', borderBottom: '1px solid #222', background: '#111' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                        <div style={{ color: '#7C6EF5', fontWeight: 'bold' }}>ПРОСМОТР ДОКУМЕНТА</div>
                        <div style={{ fontSize: '14px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{filename}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '10px' }}>
                        <button onClick={() => window.open(fileUrl)} style={{ background: '#222', border: '1px solid #333', color: '#fff', padding: '8px 15px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <Download size={16} /> Скачать
                        </button>
                        <button onClick={onClose} style={{ background: '#7C6EF5', border: 'none', color: '#fff', padding: '8px 15px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
                            Закрыть
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div style={{ flex: 1, overflow: 'auto', backgroundColor: isWord ? '#fff' : '#0a0a0f', position: 'relative' }}>
                    {isLoading && (
                        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#0a0a0f', zIndex: 10 }}>
                            <Loader2 size={40} style={{ animation: 'spin 1s linear infinite', color: '#7C6EF5' }} />
                            <p style={{ marginTop: '20px', color: '#666' }}>Загрузка...</p>
                        </div>
                    )}
                    
                    {error && (
                        <div style={{ padding: '50px', textAlign: 'center' }}>
                            <AlertCircle size={48} color="#ff4444" />
                            <h3 style={{ margin: '20px 0' }}>Не удалось загрузить файл</h3>
                            <p style={{ color: '#666' }}>{error}</p>
                        </div>
                    )}

                    {!error && (
                        <>
                            {isWord && <div ref={wordContainerRef} style={{ padding: '40px', maxWidth: '800px', margin: '0 auto', color: '#000' }} />}
                            {isExcel && excelData[activeSheet] && (
                                <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                                    <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', color: '#ccc', fontSize: '12px' }}>
                                            <tbody>
                                                {excelData[activeSheet].data.map((row, i) => (
                                                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                                                        {row.map((cell, j) => (
                                                            <td key={j} style={{ padding: '8px', borderRight: '1px solid #222', whiteSpace: 'nowrap' }}>{cell?.toString() || ''}</td>
                                                        ))}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    <div style={{ display: 'flex', gap: '10px', padding: '10px', background: '#111', overflowX: 'auto', borderTop: '1px solid #222' }}>
                                        {excelData.map((sheet, i) => (
                                            <button key={i} onClick={() => setActiveSheet(i)} style={{ padding: '5px 15px', borderRadius: '5px', background: activeSheet === i ? '#7C6EF5' : '#222', color: '#fff', border: 'none', cursor: 'pointer', fontSize: '11px', whiteSpace: 'nowrap' }}>
                                                {sheet.name}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {(isPdf || isTxt) && (
                                <iframe src={fileUrl} style={{ width: '100%', height: '100%', border: 'none', filter: isTxt ? 'invert(0.9) hue-rotate(180deg)' : 'none' }} />
                            )}
                        </>
                    )}
                </div>
            </div>
            
            <style dangerouslySetInnerHTML={{ __html: `
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                .word-preview-container .docx-wrapper { padding: 0 !important; background: transparent !important; }
            `}} />
        </div>
    );

    return createPortal(modal, document.body);
}
