import logging
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentStatus
from app.services import rag_pipeline

logger = logging.getLogger(__name__)


def update_processing_stage(db: Session, document: Document, stage: str, progress: int):
    """Update document processing stage and progress."""
    document.processing_stage = stage
    document.processing_progress = progress
    db.commit()


async def process_document_task(document_id: int, file_path: str, db: Session):
    """
    Background task to process a document.
    
    1. Pre-flight: check Ollama connectivity and model availability
    2. Parse document and extract text (PDF/DOCX/XLSX/TXT)
    3. Split into chunks
    4. Generate embeddings via Ollama (with retry)
    5. Store chunks with embeddings in database
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        logger.error(f"Document {document_id} not found")
        return
    
    try:
        logger.info(f"Starting document processing: {document_id}")
        
        # Stage 0: Pre-flight — check Ollama before doing ANY work
        update_processing_stage(db, document, "checking_ollama", 5)
        try:
            await rag_pipeline.check_ollama_health()
            await rag_pipeline.ensure_model_available(rag_pipeline.embedding_model)
        except (ConnectionError, ValueError) as e:
            raise ValueError(
                f"Ollama pre-check failed: {e}. "
                f"Ensure Ollama is running and model '{rag_pipeline.embedding_model}' is pulled."
            )
        
        # Stage 1: Extracting text
        update_processing_stage(db, document, "extracting_text", 10)
        
        page_count = rag_pipeline.get_page_count(file_path)
        document.page_count = page_count
        db.commit()
        
        pages = rag_pipeline.extract_text(file_path)
        if not pages:
            raise ValueError("No text extracted from document. The file may be empty or corrupted.")
        
        logger.info(f"Extracted {len(pages)} pages/sections from document {document_id}")
        update_processing_stage(db, document, "extracting_text", 25)
        
        # Stage 2: Chunking
        update_processing_stage(db, document, "chunking", 30)
        chunks = rag_pipeline.chunk_text(pages)
        if not chunks:
            raise ValueError("No chunks created from text. The extracted text may be too short.")
        
        document.chunk_count = len(chunks)
        db.commit()
        logger.info(f"Created {len(chunks)} chunks for document {document_id}")
        update_processing_stage(db, document, "chunking", 40)
        
        # Stage 3: Generating embeddings (with retry built into the pipeline)
        update_processing_stage(db, document, "generating_embeddings", 45)
        
        texts = [chunk["text"] for chunk in chunks]
        
        def on_progress(current: int, total: int):
            """Update progress during embedding generation."""
            progress = 45 + int(current / total * 45)  # 45-90%
            update_processing_stage(db, document, "generating_embeddings", progress)
        
        embeddings = await rag_pipeline.generate_embeddings_batch(
            texts, progress_callback=on_progress
        )
        
        # Stage 4: Storing vectors
        update_processing_stage(db, document, "storing_vectors", 92)
        
        # Combine chunks with embeddings
        processed_chunks = []
        failed_indices = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            if embedding is not None:
                processed_chunks.append({**chunk, "embedding": embedding})
            else:
                failed_indices.append(i)
        
        if failed_indices:
            logger.warning(
                f"Document {document_id}: {len(failed_indices)} chunks failed embedding "
                f"generation (indices: {failed_indices[:10]}{'...' if len(failed_indices) > 10 else ''})"
            )
        
        if not processed_chunks:
            total = len(chunks)
            raise ValueError(
                f"No chunks with valid embeddings (0/{total}). "
                f"All {total} embedding requests failed. "
                f"Check Ollama logs and ensure model '{rag_pipeline.embedding_model}' works correctly. "
                f"Test: curl {rag_pipeline.ollama_url}/api/embeddings -d '{{\"model\":\"{rag_pipeline.embedding_model}\",\"prompt\":\"test\"}}'"
            )
        
        # Store chunks in database
        for chunk_data in processed_chunks:
            chunk = DocumentChunk(
                document_id=document_id,
                text_content=chunk_data["text"],
                embedding=chunk_data["embedding"],
                page_number=chunk_data["page_number"],
                chunk_index=chunk_data["chunk_index"]
            )
            db.add(chunk)
        
        # Stage 5: Completed
        document.status = DocumentStatus.READY
        document.processing_stage = "completed"
        document.processing_progress = 100
        document.chunk_count = len(processed_chunks)
        db.commit()
        
        logger.info(
            f"Document {document_id} processed successfully: "
            f"{len(processed_chunks)} chunks created"
            f"{f' ({len(failed_indices)} failed)' if failed_indices else ''}"
        )
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        
        # Update document status to failed with detailed error message
        document.status = DocumentStatus.FAILED
        document.processing_stage = "failed"
        document.error_message = str(e)[:1000]  # Limit error message length
        db.commit()
        
        raise
