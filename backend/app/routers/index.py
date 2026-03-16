import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentChunk, DocumentStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/index", tags=["Index"])

@router.delete("")
async def clear_entire_index(db: Session = Depends(get_db)):
    # удаление всех чанков из векторной базы
    try:
        deleted_count = db.query(DocumentChunk).delete()
        db.query(Document).update(
            {
                "status": DocumentStatus.FAILED,
                "error_message": "Индекс очищен пользователем",
                "chunk_count": 0
            },
            synchronize_session=False
        )
        db.commit()
        logger.info(f"Удалено {deleted_count} чанков из индекса")
        return {"message": f"Удалено {deleted_count} чанков"}
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка очистки индекса: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{document_id}")
async def clear_document_index(document_id: int, db: Session = Depends(get_db)):
    # удаление чанков конкретного документа
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден")
        
    try:
        deleted_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        document.status = DocumentStatus.FAILED
        document.error_message = "Индекс очищен пользователем"
        document.chunk_count = 0
        db.commit()
        logger.info(f"Удалено {deleted_count} чанков для документа {document_id}")
        return {"message": f"Удалено {deleted_count} чанков"}
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка очистки индекса документа: {e}")
        raise HTTPException(status_code=500, detail=str(e))
