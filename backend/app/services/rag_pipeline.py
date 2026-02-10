import logging
from typing import List, Optional
import httpx
from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG Pipeline for document processing and embedding generation."""

    def __init__(self):
        # Table-aware separators: try to split on paragraph/line boundaries first,
        # avoiding splitting in the middle of table rows
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",      # Paragraph break (highest priority)
                "\n---\n",   # Markdown table separator
                "\n| ",      # Table row start
                "\n",        # Line break
                " ",         # Word break
                ""           # Character break (last resort)
            ]
        )
        self.ollama_url = settings.ollama_base_url
        self.embedding_model = settings.embedding_model

    def extract_text_from_pdf(self, file_path: str) -> List[dict]:
        """
        Extract text from PDF file with page numbers.
        
        Returns:
            List of dicts with 'text' and 'page_number' keys
        """
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
            
            logger.info(f"Extracted {len(pages)} pages from {file_path}")
            return pages
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise

    def get_page_count(self, file_path: str) -> int:
        """Get total page count of PDF."""
        try:
            reader = PdfReader(file_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Error getting page count: {e}")
            return 0

    def chunk_text(self, pages: List[dict]) -> List[dict]:
        """
        Split extracted pages into chunks while preserving page numbers.
        
        Returns:
            List of dicts with 'text', 'page_number', and 'chunk_index' keys
        """
        chunks = []
        chunk_index = 0
        
        for page in pages:
            page_chunks = self.text_splitter.split_text(page["text"])
            
            for chunk_text in page_chunks:
                chunks.append({
                    "text": chunk_text,
                    "page_number": page["page_number"],
                    "chunk_index": chunk_index
                })
                chunk_index += 1
        
        logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using Ollama.
        
        Returns:
            List of floats representing the embedding vector
        """
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
                return data.get("embedding")
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def generate_embeddings_batch(
        self, 
        texts: List[str]
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Note: Ollama doesn't support batch embeddings natively,
        so we process sequentially.
        """
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = await self.generate_embedding(text)
                embeddings.append(embedding)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Generated {i + 1}/{len(texts)} embeddings")
            except Exception as e:
                logger.error(f"Failed to generate embedding for chunk {i}: {e}")
                embeddings.append(None)
        
        return embeddings

    async def process_document(self, file_path: str) -> List[dict]:
        """
        Full pipeline: extract text, chunk, and generate embeddings.
        
        Returns:
            List of dicts with 'text', 'page_number', 'chunk_index', 'embedding' keys
        """
        # Extract text from PDF
        pages = self.extract_text_from_pdf(file_path)
        
        if not pages:
            raise ValueError("No text extracted from PDF")
        
        # Chunk the text
        chunks = self.chunk_text(pages)
        
        if not chunks:
            raise ValueError("No chunks created from text")
        
        # Generate embeddings
        texts = [chunk["text"] for chunk in chunks]
        embeddings = await self.generate_embeddings_batch(texts)
        
        # Combine chunks with embeddings
        processed_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is not None:
                processed_chunks.append({
                    **chunk,
                    "embedding": embedding
                })
            else:
                logger.warning(f"Skipping chunk {chunk['chunk_index']} - no embedding")
        
        logger.info(f"Successfully processed {len(processed_chunks)} chunks")
        return processed_chunks


# Singleton instance
rag_pipeline = RAGPipeline()
