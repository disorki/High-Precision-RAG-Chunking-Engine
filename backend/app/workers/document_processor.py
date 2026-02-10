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
    
    1. Parse PDF and extract text
    2. Split into chunks
    3. Generate embeddings via Ollama
    4. Store chunks with embeddings in database
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        logger.error(f"Document {document_id} not found")
        return
    
    try:
        logger.info(f"Starting document processing: {document_id}")
        
        # Stage 1: Extracting text
        update_processing_stage(db, document, "extracting_text", 10)
        
        # Get page count
        page_count = rag_pipeline.get_page_count(file_path)
        document.page_count = page_count
        db.commit()
        
        # Extract text from PDF
        pages = rag_pipeline.extract_text_from_pdf(file_path)
        if not pages:
            raise ValueError("No text extracted from PDF")
        
        update_processing_stage(db, document, "extracting_text", 25)
        
        # Stage 2: Chunking
        update_processing_stage(db, document, "chunking", 30)
        chunks = rag_pipeline.chunk_text(pages)
        if not chunks:
            raise ValueError("No chunks created from text")
        
        document.chunk_count = len(chunks)
        db.commit()
        update_processing_stage(db, document, "chunking", 40)
        
        # Stage 3: Generating embeddings
        update_processing_stage(db, document, "generating_embeddings", 45)
        
        texts = [chunk["text"] for chunk in chunks]
        embeddings = []
        
        for i, text in enumerate(texts):
            try:
                embedding = await rag_pipeline.generate_embedding(text)
                embeddings.append(embedding)
                
                # Update progress (45-90%)
                progress = 45 + int((i + 1) / len(texts) * 45)
                if (i + 1) % 10 == 0:
                    update_processing_stage(db, document, "generating_embeddings", progress)
                    logger.info(f"Generated {i + 1}/{len(texts)} embeddings for doc {document_id}")
            except Exception as e:
                logger.error(f"Failed to generate embedding for chunk {i}: {e}")
                embeddings.append(None)
        
        # Stage 4: Storing vectors
        update_processing_stage(db, document, "storing_vectors", 92)
        
        # Combine chunks with embeddings
        processed_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is not None:
                processed_chunks.append({**chunk, "embedding": embedding})
        
        if not processed_chunks:
            raise ValueError("No chunks with valid embeddings")
        
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
        )
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        
        # Update document status to failed
        document.status = DocumentStatus.FAILED
        document.processing_stage = "failed"
        document.error_message = str(e)
        db.commit()
        
        raise
