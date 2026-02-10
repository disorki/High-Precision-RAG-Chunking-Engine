import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, User, DocumentStatus
from app.schemas import UploadResponse, DocumentResponse, DocumentStatusEnum
from app.config import get_settings
from app.workers import process_document_task

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])


def get_or_create_default_user(db: Session) -> User:
    """Get or create a default user for demo purposes."""
    user = db.query(User).filter(User.email == "demo@example.com").first()
    if not user:
        user = User(email="demo@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF document for processing.
    
    - Validates file type
    - Saves file to disk
    - Creates database record
    - Triggers background processing task
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Validate file size
    contents = await file.read()
    if len(contents) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_file_size // 1024 // 1024}MB"
        )
    
    # Get or create user
    user = get_or_create_default_user(db)
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.upload_dir, unique_filename)
    
    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    # Save file
    try:
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")
    
    # Create document record
    document = Document(
        user_id=user.id,
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        status=DocumentStatus.PROCESSING
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Schedule background processing
    # We need to run the async task in the background
    def run_processing_sync():
        """Sync wrapper to run async processing task."""
        import asyncio
        # Create a new database session for the background task
        from app.database import SessionLocal
        task_db = SessionLocal()
        try:
            # Run async task in a new event loop
            asyncio.run(process_document_task(document.id, file_path, task_db))
        except Exception as e:
            logger.error(f"Background processing failed: {e}")
            # Update document status to failed
            document_to_update = task_db.query(Document).filter(Document.id == document.id).first()
            if document_to_update:
                document_to_update.status = DocumentStatus.FAILED
                document_to_update.error_message = str(e)
                task_db.commit()
        finally:
            task_db.close()
    
    background_tasks.add_task(run_processing_sync)
    
    logger.info(f"Document {document.id} uploaded, processing started")
    
    return UploadResponse(
        document_id=document.id,
        filename=file.filename,
        status=DocumentStatusEnum.PROCESSING,
        message="Document uploaded successfully. Processing started."
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get document status and details."""
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """List all documents."""
    documents = db.query(Document)\
        .order_by(Document.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return documents


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document and its chunks."""
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from disk
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
    except Exception as e:
        logger.warning(f"Failed to delete file: {e}")
    
    # Delete from database (chunks will cascade)
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}
