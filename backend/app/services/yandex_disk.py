# сервис интеграции с яндекс диском
import json
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import Document, DocumentStatus, SyncSource

logger = logging.getLogger(__name__)
settings = get_settings()

YANDEX_API_BASE = "https://cloud-api.yandex.net/v1/disk"

# поддерживаемые расширения
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt"}


class YandexDiskService:
    # работа с rest api яндекс диска

    def __init__(self, oauth_token: str):
        self.oauth_token = oauth_token
        self.headers = {"Authorization": f"OAuth {oauth_token}"}

    async def list_folder(self, folder_path: str) -> list[dict]:
        # получение списка файлов в папке
        items = []
        offset = 0
        limit = 100

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                resp = await client.get(
                    f"{YANDEX_API_BASE}/resources",
                    headers=self.headers,
                    params={
                        "path": folder_path,
                        "limit": limit,
                        "offset": offset,
                        "fields": "_embedded.items.name,_embedded.items.path,_embedded.items.size,_embedded.items.modified,_embedded.items.type,_embedded.total",
                    },
                )

                if resp.status_code == 401:
                    raise PermissionError("Неверный или просроченный токен OAuth")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Папка не найдена: {folder_path}")
                resp.raise_for_status()

                data = resp.json()
                embedded = data.get("_embedded", {})

                for item in embedded.get("items", []):
                    if item.get("type") != "file":
                        continue
                    ext = os.path.splitext(item["name"])[1].lower()
                    if ext not in SUPPORTED_EXTENSIONS:
                        continue
                    items.append({
                        "name": item["name"],
                        "path": item["path"],
                        "size": item.get("size", 0),
                        "modified": item.get("modified", ""),
                    })

                total = embedded.get("total", 0)
                offset += limit
                if offset >= total:
                    break

        return items

    async def list_folder_full(self, folder_path: str) -> dict:
        # получение списка папок и файлов
        folders = []
        files = []
        offset = 0
        limit = 100

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                resp = await client.get(
                    f"{YANDEX_API_BASE}/resources",
                    headers=self.headers,
                    params={
                        "path": folder_path,
                        "limit": limit,
                        "offset": offset,
                        "fields": "_embedded.items.name,_embedded.items.path,_embedded.items.size,_embedded.items.modified,_embedded.items.type,_embedded.total",
                    },
                )

                if resp.status_code == 401:
                    raise PermissionError("Неверный или просроченный токен OAuth")
                if resp.status_code == 404:
                    raise FileNotFoundError(f"Папка не найдена: {folder_path}")
                resp.raise_for_status()

                data = resp.json()
                embedded = data.get("_embedded", {})

                for item in embedded.get("items", []):
                    if item.get("type") == "dir":
                        folders.append({
                            "name": item["name"],
                            "path": item["path"],
                        })
                    elif item.get("type") == "file":
                        ext = os.path.splitext(item["name"])[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            files.append({
                                "name": item["name"],
                                "path": item["path"],
                                "size": item.get("size", 0),
                                "modified": item.get("modified", ""),
                                "extension": ext,
                            })

                total = embedded.get("total", 0)
                offset += limit
                if offset >= total:
                    break

        # сортировка: папки, затем файлы
        folders.sort(key=lambda x: x["name"].lower())
        files.sort(key=lambda x: x["name"].lower())

        return {"folders": folders, "files": files}

    async def download_file(self, file_path: str, save_to: str) -> str:
        # скачивание файла локально
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(
                f"{YANDEX_API_BASE}/resources/download",
                headers=self.headers,
                params={"path": file_path},
            )
            resp.raise_for_status()
            download_url = resp.json()["href"]

            resp = await client.get(download_url)
            resp.raise_for_status()

            os.makedirs(os.path.dirname(save_to), exist_ok=True)
            with open(save_to, "wb") as f:
                f.write(resp.content)

        return save_to

    async def check_connection(self) -> dict:
        # проверка токена
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{YANDEX_API_BASE}",
                headers=self.headers,
            )
            if resp.status_code == 401:
                raise PermissionError("Неверный токен OAuth")
            resp.raise_for_status()
            data = resp.json()
            return {
                "total_space": data.get("total_space", 0),
                "used_space": data.get("used_space", 0),
                "user": data.get("user", {}).get("display_name", "Unknown"),
            }


def _build_file_hash_map(files: list[dict]) -> dict:
    # построение карты хешей для списка файлов
    return {
        f["name"]: {"size": f["size"], "modified": f["modified"]}
        for f in files
    }


def _compute_diff(
    remote_files: dict, local_hashes: dict
) -> tuple[list[str], list[str], list[str]]:
    # сравнение удаленных и локальных файлов
    remote_names = set(remote_files.keys())
    local_names = set(local_hashes.keys())

    new_files = list(remote_names - local_names)
    deleted_files = list(local_names - remote_names)

    changed_files = []
    for name in remote_names & local_names:
        remote = remote_files[name]
        local = local_hashes[name]
        if remote["size"] != local["size"] or remote["modified"] != local["modified"]:
            changed_files.append(name)

    return new_files, changed_files, deleted_files


async def run_sync(source_id: int):
    # запуск синхронизации для источника
    from app.workers.document_processor import process_document_task

    db = SessionLocal()
    try:
        source = db.query(SyncSource).filter(SyncSource.id == source_id).first()
        if not source:
            logger.error(f"Источник {source_id} не найден")
            return

        token = source.oauth_token
        if not token:
            source.status = "not_connected"
            source.error_message = "Токен OAuth не установлен"
            db.commit()
            return

        source.status = "syncing"
        source.error_message = None
        db.commit()

        logger.info(f"Синхронизация источника '{source.name}' (id={source_id})")

        service = YandexDiskService(token)

        # 1. удаленные файлы
        try:
            remote_files_list = await service.list_folder(source.folder_path)
        except Exception as e:
            source.status = "error"
            source.error_message = f"Ошибка списка файлов: {str(e)[:500]}"
            db.commit()
            logger.error(f"Sync {source_id}: ошибка списка: {e}")
            return

        remote_map = _build_file_hash_map(remote_files_list)
        remote_path_map = {f["name"]: f["path"] for f in remote_files_list}

        # 2. локальное состояние
        local_hashes = json.loads(source.file_hashes) if source.file_hashes else {}
        synced_docs = json.loads(source.synced_doc_ids) if source.synced_doc_ids else {}

        # 3. разница
        new_files, changed_files, deleted_files = _compute_diff(remote_map, local_hashes)

        # 4. удаление удаленных
        for filename in deleted_files:
            doc_id = synced_docs.get(filename)
            if doc_id:
                await _delete_document(db, doc_id)
                del synced_docs[filename]
            if filename in local_hashes:
                del local_hashes[filename]

        # 5. подготовка измененных
        for filename in changed_files:
            doc_id = synced_docs.get(filename)
            if doc_id:
                await _delete_document(db, doc_id)

        # 6. скачивание
        files_to_download = new_files + changed_files
        for filename in files_to_download:
            disk_path = remote_path_map.get(filename)
            if not disk_path:
                continue

            try:
                import uuid
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                local_path = os.path.join(settings.upload_dir, unique_name)

                await service.download_file(disk_path, local_path)

                # запись документа
                doc = Document(
                    user_id=1,
                    filename=unique_name,
                    original_filename=filename,
                    file_path=local_path,
                    status=DocumentStatus.PROCESSING,
                    processing_stage="uploading",
                    processing_progress=0,
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)

                synced_docs[filename] = doc.id
                local_hashes[filename] = remote_map[filename]

                # обработка
                try:
                    await process_document_task(doc.id, local_path, db)
                except Exception as e:
                    logger.error(f"Sync {source_id}: ошибка обработки {filename}: {e}")

            except Exception as e:
                logger.error(f"Sync {source_id}: ошибка скачивания {filename}: {e}")

        # 7. обновление состояния
        source.file_hashes = json.dumps(local_hashes)
        source.synced_doc_ids = json.dumps(synced_docs)
        source.last_synced_at = datetime.utcnow()
        source.status = "idle"
        source.error_message = None
        db.commit()

    except Exception as e:
        logger.error(f"Sync {source_id} failed: {e}")
        try:
            source = db.query(SyncSource).filter(SyncSource.id == source_id).first()
            if source:
                source.status = "error"
                source.error_message = str(e)[:500]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def _delete_document(db: Session, doc_id: int):
    # удаление документа и данных
    from sqlalchemy import text

    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        file_path = doc.file_path

        db.execute(text("""
            DELETE FROM chat_messages WHERE session_id IN (
                SELECT id FROM chat_sessions WHERE document_id = :doc_id
            )
        """), {"doc_id": doc_id})
        db.execute(text("DELETE FROM chat_sessions WHERE document_id = :doc_id"), {"doc_id": doc_id})
        db.execute(text("DELETE FROM document_chunks WHERE document_id = :doc_id"), {"doc_id": doc_id})
        db.execute(text("DELETE FROM documents WHERE id = :doc_id"), {"doc_id": doc_id})
        db.commit()

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления документа {doc_id}: {e}")
