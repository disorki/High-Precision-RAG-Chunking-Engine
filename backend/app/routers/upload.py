import os
import uuid
import zipfile
import tempfile
import shutil
import logging
import mimetypes
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Document, User, DocumentStatus
from app.schemas import UploadResponse, UploadBatchResponse, DocumentResponse, DocumentStatusEnum
from app.config import get_settings
from app.workers import process_document_task
from app.services.rag_pipeline import SUPPORTED_EXTENSIONS

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.txt': 'text/plain',
}

ARCHIVE_EXTENSIONS = {'.zip', '.rar'}


def get_or_create_default_user(db: Session) -> User:
    """Get or create a default user for demo purposes."""
    user = db.query(User).filter(User.email == "demo@example.com").first()
    if not user:
        user = User(email="demo@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def extract_archive(file_path: str, extract_dir: str) -> List[str]:
    """
    Extract files from a ZIP or RAR archive.
    Returns a list of extracted file paths that are supported document types.
    """
    extracted_files = []
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.zip':
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.extractall(extract_dir)
        elif ext == '.rar':
            try:
                import rarfile
                with rarfile.RarFile(file_path, 'r') as rf:
                    rf.extractall(extract_dir)
            except ImportError:
                logger.error("rarfile not installed. Cannot extract RAR archives.")
                return []

        # Walk extracted directory and collect supported files
        for root, dirs, files in os.walk(extract_dir):
            for fname in files:
                if fname.startswith('._') or fname.startswith('__MACOSX'):
                    continue
                file_ext = os.path.splitext(fname)[1].lower()
                if file_ext in SUPPORTED_EXTENSIONS:
                    extracted_files.append(os.path.join(root, fname))

    except Exception as e:
        logger.error(f"Archive extraction failed: {e}")

    return extracted_files


def _create_background_task(doc_id: int, file_path: str):
    """Factory for background processing tasks (avoids closure bugs in loops)."""
    def run_processing_sync():
        import asyncio
        from app.database import SessionLocal
        task_db = SessionLocal()
        try:
            asyncio.run(process_document_task(doc_id, file_path, task_db))
        except Exception as e:
            logger.error(f"Background processing failed for doc {doc_id}: {e}")
            doc = task_db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = str(e)
                task_db.commit()
        finally:
            task_db.close()
    return run_processing_sync


def _save_and_register_file(
    file_bytes: bytes,
    original_filename: str,
    user_id: int,
    db: Session,
    background_tasks: BackgroundTasks
) -> UploadResponse:
    """Save a single file to disk, create DB record, schedule processing."""
    file_extension = os.path.splitext(original_filename)[1].lower()

    if file_extension not in SUPPORTED_EXTENSIONS:
        return UploadResponse(
            document_id=0,
            filename=original_filename,
            status=DocumentStatusEnum.FAILED,
            message=f"Unsupported file type: {file_extension}"
        )

    if len(file_bytes) > settings.max_file_size:
        return UploadResponse(
            document_id=0,
            filename=original_filename,
            status=DocumentStatusEnum.FAILED,
            message="File too large"
        )

    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.upload_dir, unique_filename)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    document = Document(
        user_id=user_id,
        filename=unique_filename,
        original_filename=original_filename,
        file_path=file_path,
        status=DocumentStatus.PROCESSING
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(_create_background_task(document.id, file_path))

    return UploadResponse(
        document_id=document.id,
        filename=original_filename,
        status=DocumentStatusEnum.PROCESSING,
        message="Processing started"
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a single document for processing."""
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    contents = await file.read()
    if len(contents) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_file_size // 1024 // 1024}MB"
        )

    user = get_or_create_default_user(db)
    os.makedirs(settings.upload_dir, exist_ok=True)

    result = _save_and_register_file(contents, file.filename, user.id, db, background_tasks)
    logger.info(f"Document {result.document_id} uploaded, processing started")
    return result


@router.post("/upload/batch", response_model=UploadBatchResponse)
async def upload_documents_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload multiple documents at once.
    Supports: individual files (PDF, DOCX, XLSX, TXT) and archives (ZIP, RAR).
    Archives are automatically extracted and all supported files inside are processed.
    """
    user = get_or_create_default_user(db)
    os.makedirs(settings.upload_dir, exist_ok=True)

    results: List[UploadResponse] = []

    for file in files:
        try:
            file_extension = os.path.splitext(file.filename)[1].lower()
            contents = await file.read()

            if file_extension in ARCHIVE_EXTENSIONS:
                # Handle archive: extract and process each file inside
                tmp_dir = tempfile.mkdtemp()
                archive_path = os.path.join(tmp_dir, file.filename)
                try:
                    with open(archive_path, "wb") as f:
                        f.write(contents)

                    extract_dir = os.path.join(tmp_dir, "extracted")
                    os.makedirs(extract_dir, exist_ok=True)
                    extracted_files = extract_archive(archive_path, extract_dir)

                    if not extracted_files:
                        results.append(UploadResponse(
                            document_id=0,
                            filename=file.filename,
                            status=DocumentStatusEnum.FAILED,
                            message="No supported files found in archive"
                        ))
                        continue

                    for extracted_path in extracted_files:
                        with open(extracted_path, "rb") as ef:
                            file_bytes = ef.read()
                        original_name = os.path.basename(extracted_path)
                        result = _save_and_register_file(
                            file_bytes, original_name, user.id, db, background_tasks
                        )
                        results.append(result)

                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

            elif file_extension in SUPPORTED_EXTENSIONS:
                result = _save_and_register_file(
                    contents, file.filename, user.id, db, background_tasks
                )
                results.append(result)
            else:
                results.append(UploadResponse(
                    document_id=0,
                    filename=file.filename,
                    status=DocumentStatusEnum.FAILED,
                    message=f"Unsupported file type: {file_extension}"
                ))

        except Exception as e:
            logger.error(f"Failed to process file {file.filename} in batch: {e}")
            results.append(UploadResponse(
                document_id=0,
                filename=file.filename,
                status=DocumentStatusEnum.FAILED,
                message=str(e)
            ))

    successful = sum(1 for r in results if r.status == DocumentStatusEnum.PROCESSING)
    return UploadBatchResponse(
        results=results,
        message=f"Batch complete: {successful} files processing, {len(results) - successful} failed."
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


@router.get("/documents/{document_id}/file")
async def get_document_file(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Download/preview the original document file."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    file_extension = os.path.splitext(document.original_filename)[1].lower()
    content_type = MIME_TYPES.get(file_extension, 'application/octet-stream')

    return FileResponse(
        path=document.file_path,
        media_type=content_type,
        filename=document.original_filename,
        headers={
            "Content-Disposition": f"inline; filename=\"{document.original_filename}\""
        }
    )


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


@router.delete("/documents/failed")
async def delete_failed_documents(db: Session = Depends(get_db)):
    """Delete all documents with 'failed' status and their related data."""
    from sqlalchemy import text

    try:
        # Find all failed document IDs
        failed_docs = db.execute(text(
            "SELECT id, file_path FROM documents WHERE status::text = 'failed'"
        )).fetchall()

        if not failed_docs:
            return {"message": "No failed documents to delete", "deleted_count": 0}

        doc_ids = [row.id for row in failed_docs]
        file_paths = [row.file_path for row in failed_docs]

        # Delete in FK order for all failed docs at once
        db.execute(text("""
            DELETE FROM chat_messages
            WHERE session_id IN (
                SELECT id FROM chat_sessions WHERE document_id = ANY(:doc_ids)
            )
        """), {"doc_ids": doc_ids})

        db.execute(text(
            "DELETE FROM chat_sessions WHERE document_id = ANY(:doc_ids)"
        ), {"doc_ids": doc_ids})

        db.execute(text(
            "DELETE FROM document_chunks WHERE document_id = ANY(:doc_ids)"
        ), {"doc_ids": doc_ids})

        db.execute(text(
            "DELETE FROM documents WHERE id = ANY(:doc_ids)"
        ), {"doc_ids": doc_ids})

        db.commit()

        # Clean up files from disk
        for fp in file_paths:
            try:
                if fp and os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                pass

        logger.info(f"Batch deleted {len(doc_ids)} failed documents")
        return {"message": f"Deleted {len(doc_ids)} failed documents", "deleted_count": len(doc_ids)}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to batch delete failed documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document, its chunks, chat sessions, and file."""
    from sqlalchemy import text

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = document.file_path

    try:
        # Use raw SQL to delete in strict FK order to avoid constraint violations
        # 1. Delete chat messages for all sessions linked to this document
        db.execute(text("""
            DELETE FROM chat_messages
            WHERE session_id IN (
                SELECT id FROM chat_sessions WHERE document_id = :doc_id
            )
        """), {"doc_id": document_id})

        # 2. Delete chat sessions linked to this document
        db.execute(text(
            "DELETE FROM chat_sessions WHERE document_id = :doc_id"
        ), {"doc_id": document_id})

        # 3. Delete document chunks
        db.execute(text(
            "DELETE FROM document_chunks WHERE document_id = :doc_id"
        ), {"doc_id": document_id})

        # 4. Delete the document record itself
        db.execute(text(
            "DELETE FROM documents WHERE id = :doc_id"
        ), {"doc_id": document_id})

        db.commit()

        # 5. Delete file from disk (after successful DB commit)
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file from disk: {e}")

        logger.info(f"Document {document_id} fully deleted")
        return {"message": "Document deleted successfully"}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
