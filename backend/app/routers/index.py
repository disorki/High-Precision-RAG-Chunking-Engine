import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentChunk, DocumentStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/index", tags=["Index"])

@router.delete("")
async def clear_entire_index(db: Session = Depends(get_db)):
    """
    Delete all chunks from the vector database.
    Retains the original document records and files, but updates their status.
    """
    try:
        deleted_count = db.query(DocumentChunk).delete()
        db.query(Document).update(
            {
                "status": DocumentStatus.FAILED,
                "error_message": "Index cleared by user (chunks deleted)",
                "chunk_count": 0
            },
            synchronize_session=False
        )
        db.commit()
        logger.info(f"Deleted {deleted_count} chunks from index")
        return {"message": f"Successfully deleted {deleted_count} chunks from the entire index"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear index: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{document_id}")
async def clear_document_index(document_id: int, db: Session = Depends(get_db)):
    """
    Delete chunks for a specific document from the vector database.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    try:
        deleted_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        document.status = DocumentStatus.FAILED
        document.error_message = "Index cleared by user (chunks deleted)"
        document.chunk_count = 0
        db.commit()
        logger.info(f"Deleted {deleted_count} chunks for document {document_id}")
        return {"message": f"Successfully deleted {deleted_count} chunks for document {document_id}"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear document index: {e}")
        raise HTTPException(status_code=500, detail=str(e))
