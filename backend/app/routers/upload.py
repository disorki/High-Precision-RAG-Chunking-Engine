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
    # получение или создание тестового пользователя
    user = db.query(User).filter(User.email == "demo@example.com").first()
    if not user:
        user = User(email="demo@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def extract_archive(file_path: str, extract_dir: str) -> List[str]:
    # распаковка zip или rar архива
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
                logger.error("rarfile не установлен")
                return []

        # сбор поддерживаемых файлов из архива
        for root, dirs, files in os.walk(extract_dir):
            for fname in files:
                if fname.startswith('._') or fname.startswith('__MACOSX'):
                    continue
                file_ext = os.path.splitext(fname)[1].lower()
                if file_ext in SUPPORTED_EXTENSIONS:
                    extracted_files.append(os.path.join(root, fname))

    except Exception as e:
        logger.error(f"Ошибка распаковки архива: {e}")

    return extracted_files


def _create_background_task(doc_id: int, file_path: str):
    # фоновая задача для обработки документа
    def run_processing_sync():
        import asyncio
        from app.database import SessionLocal
        task_db = SessionLocal()
        try:
            asyncio.run(process_document_task(doc_id, file_path, task_db))
        except Exception as e:
            logger.error(f"Ошибка фоновой обработки документа {doc_id}: {e}")
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
    # сохранение файла на диск и регистрация в базе
    file_extension = os.path.splitext(original_filename)[1].lower()

    if file_extension not in SUPPORTED_EXTENSIONS:
        return UploadResponse(
            document_id=0,
            filename=original_filename,
            status=DocumentStatusEnum.FAILED,
            message=f"Неподдерживаемый тип файла: {file_extension}"
        )

    if len(file_bytes) > settings.max_file_size:
        return UploadResponse(
            document_id=0,
            filename=original_filename,
            status=DocumentStatusEnum.FAILED,
            message="Файл слишком большой"
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
        message="Обработка запущена"
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # загрузка одиночного документа
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат. Список: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    contents = await file.read()
    if len(contents) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Файл великоват. Лимит: {settings.max_file_size // 1024 // 1024}MB"
        )

    user = get_or_create_default_user(db)
    os.makedirs(settings.upload_dir, exist_ok=True)

    result = _save_and_register_file(contents, file.filename, user.id, db, background_tasks)
    logger.info(f"Документ {result.document_id} загружен, обработка началась")
    return result


@router.post("/upload/batch", response_model=UploadBatchResponse)
async def upload_documents_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    # массовая загрузка документов и архивов
    user = get_or_create_default_user(db)
    os.makedirs(settings.upload_dir, exist_ok=True)

    results: List[UploadResponse] = []

    for file in files:
        try:
            file_extension = os.path.splitext(file.filename)[1].lower()
            contents = await file.read()

            if file_extension in ARCHIVE_EXTENSIONS:
                # обработка архива: распаковка и импорт каждого файла
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
                            message="В архиве нет подходящих файлов"
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
                    message=f"Формат не поддерживается: {file_extension}"
                ))

        except Exception as e:
            logger.error(f"Ошибка обработки файла {file.filename}: {e}")
            results.append(UploadResponse(
                document_id=0,
                filename=file.filename,
                status=DocumentStatusEnum.FAILED,
                message=str(e)
            ))

    successful = sum(1 for r in results if r.status == DocumentStatusEnum.PROCESSING)
    return UploadBatchResponse(
        results=results,
        message=f"Пакетная загрузка завершена: {successful} в обработке, {len(results) - successful} с ошибкой"
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    # статус и детали документа
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return document


@router.get("/documents/{document_id}/file")
async def get_document_file(
    document_id: int,
    db: Session = Depends(get_db)
):
    # скачивание или просмотр файла
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден")
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="Файл отсутствует на диске")

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
    limit: int = 500,
    db: Session = Depends(get_db)
):
    # список всех документов
    documents = db.query(Document)\
        .order_by(Document.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return documents


@router.delete("/documents/failed")
async def delete_failed_documents(db: Session = Depends(get_db)):
    # удаление всех документов со статусом 'failed'
    from sqlalchemy import text

    try:
        # поиск id упавших документов
        failed_docs = db.execute(text(
            "SELECT id, file_path FROM documents WHERE status::text = 'failed'"
        )).fetchall()

        if not failed_docs:
            return {"message": "Нет документов для удаления", "deleted_count": 0}

        doc_ids = [row.id for row in failed_docs]
        file_paths = [row.file_path for row in failed_docs]

        # удаление связанных данных
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

        # удаление файлов с диска
        for fp in file_paths:
            try:
                if fp and os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                pass

        logger.info(f"Удалено {len(doc_ids)} упавших документов")
        return {"message": f"Удалено {len(doc_ids)} документов", "deleted_count": len(doc_ids)}

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при массовом удалении документов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    # удаление документа, его чанков и сессий чата
    from sqlalchemy import text

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден")

    file_path = document.file_path

    try:
        # удаление в строгом порядке для соблюдения ограничений fk
        db.execute(text("""
            DELETE FROM chat_messages
            WHERE session_id IN (
                SELECT id FROM chat_sessions WHERE document_id = :doc_id
            )
        """), {"doc_id": document_id})

        db.execute(text(
            "DELETE FROM chat_sessions WHERE document_id = :doc_id"
        ), {"doc_id": document_id})

        db.execute(text(
            "DELETE FROM document_chunks WHERE document_id = :doc_id"
        ), {"doc_id": document_id})

        db.execute(text(
            "DELETE FROM documents WHERE id = :doc_id"
        ), {"doc_id": document_id})

        db.commit()

        # удаление файла
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Ошибка удаления файла с диска: {e}")

        logger.info(f"Документ {document_id} удален")
        return {"message": "Документ успешно удален"}

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления документа {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления: {str(e)}")
