import os
import re
import asyncio
import logging
import uuid
from typing import List, Optional, Callable
import httpx
from pypdf import PdfReader
from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
from openpyxl import load_workbook
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.txt'}


def get_file_extension(file_path: str) -> str:
    """Get lowercase file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext


class RAGPipeline:
    """RAG Pipeline for document processing and embedding generation."""

    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",      # Paragraph break (highest priority)
                "\n---\n",   # Markdown table separator
                "\n| ",      # Table row start
                "\n",        # Line break
                ". ",        # Sentence break
                " ",         # Word break
                ""           # Character break (last resort)
            ]
        )
        self.ollama_url = settings.ollama_base_url
        self.embedding_model = settings.embedding_model
        self.retry_count = settings.embedding_retry_count
        self.retry_delay = settings.embedding_retry_delay

    # ── Ollama Health & Model Checks ─────────────────────────────────

    async def check_ollama_health(self) -> bool:
        """
        Check if Ollama is reachable.
        Returns True if healthy, raises an error with a clear message if not.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/version")
                response.raise_for_status()
                version_info = response.json()
                logger.info(f"Ollama is healthy: version {version_info.get('version', 'unknown')}")
                return True
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.ollama_url}. "
                f"Make sure Ollama is running. If using Docker: docker exec -it rag-ollama ollama --version"
            )
        except httpx.TimeoutException:
            raise ConnectionError(
                f"Ollama at {self.ollama_url} is not responding (timeout). "
                f"The service may be starting up — try again in a moment."
            )
        except Exception as e:
            raise ConnectionError(f"Ollama health check failed: {e}")

    async def ensure_model_available(self, model_name: str) -> bool:
        """
        Check if a model is available in Ollama.
        Raises a clear error if the model is not pulled.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/show",
                    json={"name": model_name}
                )
                if response.status_code == 200:
                    logger.info(f"Model '{model_name}' is available")
                    return True
                else:
                    raise ValueError(
                        f"Model '{model_name}' is not available in Ollama. "
                        f"Pull it first: ollama pull {model_name}"
                    )
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.ollama_url} to check model '{model_name}'"
            )
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Could not verify model '{model_name}': {e}")
            return True  # Optimistically proceed

    # ── PDF ───────────────────────────────────────────────────────────

    def extract_text_from_pdf(self, file_path: str) -> List[dict]:
        """Extract text from PDF file with page numbers."""
        try:
            reader = PdfReader(file_path)
            pages = []

            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append({
                        "text": text.strip(),
                        "page_number": i + 1
                    })

            logger.info(f"Extracted {len(pages)} pages from PDF: {file_path}")
            return pages
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise

    def get_pdf_page_count(self, file_path: str) -> int:
        """Get total page count of PDF."""
        try:
            reader = PdfReader(file_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Error getting PDF page count: {e}")
            return 0

    # ── DOCX ──────────────────────────────────────────────────────────

    def _iter_block_items(self, doc: DocxDocument):
        """
        Yield each paragraph and table in document order.
        This properly interleaves paragraphs and tables
        (unlike iterating doc.paragraphs and doc.tables separately).
        """
        body = doc.element.body
        for child in body:
            if child.tag == qn('w:p'):
                yield Paragraph(child, body)
            elif child.tag == qn('w:tbl'):
                yield DocxTable(child, body)

    def _table_to_text(self, table: DocxTable) -> str:
        """Convert a DOCX table to a readable text representation."""
        rows_text = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows_text.append(" | ".join(cells))
        return "\n".join(rows_text)

    def extract_text_from_docx(self, file_path: str) -> List[dict]:
        """
        Extract text from Word (.docx) file.
        Tables and paragraphs are extracted in correct document order.
        Content is split into virtual 'pages' of ~3000 chars.
        """
        try:
            doc = DocxDocument(file_path)
            pages = []
            current_text_parts = []
            page_number = 1
            char_count = 0

            for block in self._iter_block_items(doc):
                if isinstance(block, Paragraph):
                    text = block.text.strip()
                    if not text:
                        continue
                    current_text_parts.append(text)
                    char_count += len(text)

                elif isinstance(block, DocxTable):
                    table_text = self._table_to_text(block)
                    if table_text.strip():
                        current_text_parts.append(f"\n[Таблица]\n{table_text}\n")
                        char_count += len(table_text)

                # Split into "pages" of ~3000 chars
                if char_count >= 3000:
                    pages.append({
                        "text": "\n".join(current_text_parts),
                        "page_number": page_number
                    })
                    current_text_parts = []
                    char_count = 0
                    page_number += 1

            # Add remaining content
            if current_text_parts:
                pages.append({
                    "text": "\n".join(current_text_parts),
                    "page_number": page_number
                })

            logger.info(f"Extracted {len(pages)} sections from DOCX: {file_path}")
            return pages
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}")
            raise

    # ── XLSX ──────────────────────────────────────────────────────────

    def extract_text_from_xlsx(self, file_path: str) -> List[dict]:
        """
        Extract text from Excel (.xlsx) file.
        Each worksheet becomes a separate 'page'.
        """
        try:
            wb = load_workbook(file_path, read_only=True, data_only=True)
            pages = []

            for sheet_index, sheet_name in enumerate(wb.sheetnames):
                ws = wb[sheet_name]
                rows_text = []

                for row in ws.iter_rows(values_only=True):
                    cell_values = []
                    for cell in row:
                        if cell is not None:
                            cell_values.append(str(cell).strip())
                        else:
                            cell_values.append("")

                    if any(v for v in cell_values):
                        rows_text.append(" | ".join(cell_values))

                if rows_text:
                    sheet_text = f"[Лист: {sheet_name}]\n" + "\n".join(rows_text)
                    pages.append({
                        "text": sheet_text,
                        "page_number": sheet_index + 1
                    })

            wb.close()
            logger.info(f"Extracted {len(pages)} sheets from XLSX: {file_path}")
            return pages
        except Exception as e:
            logger.error(f"Error extracting XLSX text: {e}")
            raise

    # ── TXT ───────────────────────────────────────────────────────────

    def extract_text_from_txt(self, file_path: str) -> List[dict]:
        """
        Extract text from a plain text (.txt) file.
        Splits into virtual pages of ~3000 chars.
        """
        try:
            encodings = ['utf-8', 'cp1251', 'latin-1']
            content = None
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if content is None:
                raise ValueError("Could not decode text file with any supported encoding")

            if not content.strip():
                return []

            pages = []
            page_size = 3000
            paragraphs = content.split('\n\n')
            current_parts = []
            char_count = 0
            page_number = 1

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                current_parts.append(para)
                char_count += len(para)

                if char_count >= page_size:
                    pages.append({
                        "text": "\n\n".join(current_parts),
                        "page_number": page_number
                    })
                    current_parts = []
                    char_count = 0
                    page_number += 1

            if current_parts:
                pages.append({
                    "text": "\n\n".join(current_parts),
                    "page_number": page_number
                })

            logger.info(f"Extracted {len(pages)} sections from TXT: {file_path}")
            return pages
        except Exception as e:
            logger.error(f"Error extracting TXT text: {e}")
            raise

    # ── Universal Methods ─────────────────────────────────────────────

    def extract_text(self, file_path: str) -> List[dict]:
        """Extract text from a file, auto-detecting format by extension."""
        ext = get_file_extension(file_path)

        if ext == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif ext == '.docx':
            return self.extract_text_from_docx(file_path)
        elif ext == '.xlsx':
            return self.extract_text_from_xlsx(file_path)
        elif ext == '.txt':
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def get_page_count(self, file_path: str) -> int:
        """Get page/section/sheet count depending on file type."""
        ext = get_file_extension(file_path)

        if ext == '.pdf':
            return self.get_pdf_page_count(file_path)
        elif ext == '.docx':
            try:
                doc = DocxDocument(file_path)
                para_count = len([p for p in doc.paragraphs if p.text.strip()])
                return max(1, para_count // 30 + (1 if para_count % 30 else 0))
            except Exception:
                return 1
        elif ext == '.xlsx':
            try:
                wb = load_workbook(file_path, read_only=True)
                count = len(wb.sheetnames)
                wb.close()
                return count
            except Exception:
                return 1
        elif ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return max(1, len(content) // 3000 + 1)
            except Exception:
                return 1
        else:
            return 0

    def chunk_text(self, pages: List[dict], filename: str = None) -> List[dict]:
        """Split extracted pages into chunks while preserving page numbers and adding UUIDs."""
        chunks = []
        chunk_index = 0

        for page in pages:
            page_text = page["text"].strip()
            if not page_text:
                continue

            page_chunks = self.text_splitter.split_text(page_text)

            for chunk_text in page_chunks:
                chunk_text = chunk_text.strip()
                if not chunk_text:
                    continue
                chunks.append({
                    "chunk_uuid": str(uuid.uuid4()),
                    "text": chunk_text,
                    "page_number": page["page_number"],
                    "chunk_index": chunk_index,
                    "source_filename": filename
                })
                chunk_index += 1

        logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks

    async def generate_context_header(self, text: str) -> Optional[str]:
        """
        Generate a brief summarizing header via LLM for a text chunk.
        Raises exceptions on failure, designed to be retried by the caller.
        """
        if not settings.enable_context_headers:
            return None

        prompt = (
            f"Write a very brief (15-20 words) descriptive context header "
            f"summarizing the main topic of this text chunk. Output ONLY the header.\n\n"
            f"Chunk:\n{text}\n\nHeader:"
        )

        last_error = None
        for attempt in range(self.retry_count):
            try:
                # We use a longer timeout since generation takes more time than embeddings
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": settings.chat_model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.1, "num_ctx": 4096}
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    header = data.get("response", "").strip()
                    if not header:
                        raise ValueError("Ollama returned empty response for context header.")
                    return header

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(
                    f"Context header attempt {attempt + 1}/{self.retry_count} failed "
                    f"(transient: {type(e).__name__}). Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            except httpx.HTTPStatusError as e:
                # Non-retryable
                if e.response.status_code == 404:
                    raise ValueError(f"Model '{settings.chat_model}' not found in Ollama.")
                last_error = e
                wait_time = self.retry_delay * (2 ** attempt)
                await asyncio.sleep(wait_time)
            except Exception as e:
                last_error = e
                logger.error(f"Context header generation error: {e}")
                raise

        raise ConnectionError(f"Failed to generate context header. Last error: {last_error}")

    async def generate_context_headers_batch(
        self,
        texts: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Optional[str]]:
        """
        Generate context headers for multiple texts.
        Uses a semaphore to limit concurrency based on settings.
        """
        if not settings.enable_context_headers:
            return [None] * len(texts)

        headers: List[Optional[str]] = [None] * len(texts)
        state = {"failed": 0, "completed": 0}
        
        sem = asyncio.Semaphore(settings.embedding_concurrency)

        async def process_one(idx: int, text: str):
            async with sem:
                try:
                    header = await self.generate_context_header(text)
                    headers[idx] = header
                except Exception as e:
                    logger.error(f"Failed to generate context header for chunk {idx}: {e}")
                    state["failed"] += 1
                
                state["completed"] += 1
                if progress_callback and state["completed"] % 5 == 0:
                    progress_callback(state["completed"], len(texts))

        tasks = [process_one(i, txt) for i, txt in enumerate(texts)]
        await asyncio.gather(*tasks)

        if state["failed"] > 0:
            logger.warning(f"Context headers generation: {state['failed']}/{len(texts)} failed")
        else:
            logger.info(f"Successfully generated {len(texts)} context headers")

        return headers

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using Ollama with retry logic.
        Retries on transient errors (connection, timeout) with exponential backoff.
        """
        last_error = None

        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.ollama_url}/api/embeddings",
                        json={
                            "model": self.embedding_model,
                            "prompt": text
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    embedding = data.get("embedding")
                    if embedding is None:
                        raise ValueError(f"Ollama returned no embedding. Response: {data}")
                    return embedding

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(
                    f"Embedding attempt {attempt + 1}/{self.retry_count} failed "
                    f"(transient: {type(e).__name__}). Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except httpx.HTTPStatusError as e:
                # Non-retryable HTTP errors (e.g. model not found = 404)
                if e.response.status_code == 404:
                    raise ValueError(
                        f"Model '{self.embedding_model}' not found in Ollama. "
                        f"Pull it: ollama pull {self.embedding_model}"
                    )
                last_error = e
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(
                    f"Embedding attempt {attempt + 1}/{self.retry_count} failed "
                    f"(HTTP {e.response.status_code}). Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                last_error = e
                logger.error(f"Embedding generation error: {e}")
                raise

        # All retries exhausted
        raise ConnectionError(
            f"Failed to generate embedding after {self.retry_count} attempts. "
            f"Last error: {last_error}"
        )

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts concurrently.
        Uses a semaphore to limit concurrency based on settings.
        """
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        state = {"failed": 0, "completed": 0}
        
        sem = asyncio.Semaphore(settings.embedding_concurrency)

        async def process_one(idx: int, text: str):
            async with sem:
                try:
                    embedding = await self.generate_embedding(text)
                    embeddings[idx] = embedding
                except Exception as e:
                    logger.error(
                        f"Failed to generate embedding for chunk {idx} "
                        f"(text preview: '{text[:80]}...'): {e}"
                    )
                    state["failed"] += 1
                
                state["completed"] += 1
                if progress_callback and state["completed"] % 5 == 0:
                    progress_callback(state["completed"], len(texts))
                if state["completed"] % 10 == 0:
                    logger.info(f"Generated {state['completed']}/{len(texts)} embeddings ({state['failed']} failed)")

        tasks = [process_one(i, txt) for i, txt in enumerate(texts)]
        await asyncio.gather(*tasks)

        if state["failed"] > 0:
            logger.warning(f"Embedding generation: {state['failed']}/{len(texts)} failed")

        return embeddings

    async def process_document(self, file_path: str) -> List[dict]:
        """
        Full pipeline: health check, extract text, chunk, and generate embeddings.
        """
        # Pre-flight checks
        await self.check_ollama_health()
        await self.ensure_model_available(self.embedding_model)

        # Extract text
        pages = self.extract_text(file_path)
        if not pages:
            raise ValueError("No text extracted from document")

        # Chunk
        chunks = self.chunk_text(pages)
        if not chunks:
            raise ValueError("No chunks created from text")

        # Generate embeddings
        texts = [chunk["text"] for chunk in chunks]
        embeddings = await self.generate_embeddings_batch(texts)

        # Combine
        processed_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is not None:
                processed_chunks.append({**chunk, "embedding": embedding})
            else:
                logger.warning(f"Skipping chunk {chunk['chunk_index']} - no embedding")

        logger.info(f"Successfully processed {len(processed_chunks)} chunks")
        return processed_chunks


# Singleton instance
rag_pipeline = RAGPipeline()
