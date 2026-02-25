"""
API router for Yandex Disk sync sources management with OAuth flow.

Uses the "verification_code" redirect — user enters code from Yandex page.
Flow: auth first (exchange code → get token), then create source with token.
"""
import logging
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import httpx

from app.database import get_db
from app.models import SyncSource
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api", tags=["sync"])

YANDEX_AUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"


# --- OAuth Flow ---

@router.get("/yandex/auth-url")
async def get_auth_url():
    """Generate Yandex OAuth URL."""
    if not settings.yandex_client_id:
        raise HTTPException(status_code=400, detail="YANDEX_CLIENT_ID not configured")

    url = (
        f"{YANDEX_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={settings.yandex_client_id}"
    )
    return {"url": url, "client_id": settings.yandex_client_id}


@router.post("/yandex/exchange-code")
async def exchange_code(
    data: dict,
    db: Session = Depends(get_db),
):
    """
    Exchange authorization code for token.
    If source_id is provided, saves token to that source.
    If not, just returns the token and user info (for auth-first flow).
    """
    code = data.get("code", "").strip()
    source_id = data.get("source_id", 0)

    if not code:
        raise HTTPException(status_code=400, detail="Code is required")

    # Exchange code for token
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                YANDEX_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.yandex_client_id,
                    "client_secret": settings.yandex_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Yandex API error: {str(e)}")

    if resp.status_code != 200:
        err = resp.json()
        detail = err.get("error_description", err.get("error", resp.text))
        raise HTTPException(status_code=400, detail=f"Token error: {detail}")

    token_data = resp.json()
    access_token = token_data.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access_token in response")

    # Get Yandex user info
    user_name = "Пользователь"
    try:
        from app.services.yandex_disk import YandexDiskService
        svc = YandexDiskService(access_token)
        info = await svc.check_connection()
        user_name = info.get("user", user_name)
    except Exception:
        pass

    # If source_id provided, save token to existing source
    if source_id:
        source = db.query(SyncSource).filter(SyncSource.id == source_id).first()
        if source:
            source.oauth_token = access_token
            source.yandex_user = user_name
            source.status = "idle"
            source.error_message = None
            db.commit()
            _register_in_scheduler(source)
            logger.info(f"OAuth connected for source {source_id}: user={user_name}")
            return {
                "success": True,
                "user": user_name,
                "token": access_token,
                "source": _source_to_dict(source),
            }

    # No source_id — just return token (auth-first flow)
    logger.info(f"OAuth token obtained for user={user_name}")
    return {
        "success": True,
        "user": user_name,
        "token": access_token,
    }


# --- File Browser ---

@router.post("/yandex/browse")
async def browse_yandex_disk(data: dict):
    """Browse files and folders on Yandex Disk at a given path."""
    token = data.get("token", "").strip()
    path = data.get("path", "/").strip() or "/"

    if not token:
        raise HTTPException(status_code=400, detail="Token is required")

    try:
        from app.services.yandex_disk import YandexDiskService
        svc = YandexDiskService(token)
        result = await svc.list_folder_full(path)
        return {"path": path, **result}
    except PermissionError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/yandex/import-file")
async def import_yandex_file(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Download a file from Yandex Disk and process it as a document."""
    token = data.get("token", "").strip()
    file_path = data.get("file_path", "").strip()
    file_name = data.get("file_name", "").strip()

    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")
    if not file_name:
        file_name = os.path.basename(file_path)

    try:
        from app.services.yandex_disk import YandexDiskService
        svc = YandexDiskService(token)

        # Download to temp location
        file_ext = os.path.splitext(file_name)[1].lower()
        temp_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{file_ext}")
        await svc.download_file(file_path, temp_path)

        # Read downloaded bytes and use upload pipeline
        with open(temp_path, "rb") as f:
            file_bytes = f.read()

        # Remove temp file — _save_and_register_file will save its own copy
        os.remove(temp_path)

        from app.routers.upload import _save_and_register_file, get_or_create_default_user
        user = get_or_create_default_user(db)
        result = _save_and_register_file(file_bytes, file_name, user.id, db, background_tasks)

        return {
            "document_id": result.document_id,
            "filename": result.filename,
            "status": result.status,
            "message": result.message,
        }

    except PermissionError:
        raise HTTPException(status_code=401, detail="Yandex token expired")
    except Exception as e:
        logger.error(f"Yandex import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


# --- Sync Sources CRUD ---

@router.get("/sync-sources")
async def list_sync_sources(db: Session = Depends(get_db)):
    sources = db.query(SyncSource).order_by(SyncSource.created_at.desc()).all()
    return [_source_to_dict(s) for s in sources]


@router.post("/sync-sources")
async def create_sync_source(data: dict, db: Session = Depends(get_db)):
    """Create a new sync source. Accepts optional oauth_token/yandex_user
    to create an already-connected source (auth-first flow)."""
    name = data.get("name", "").strip()
    folder_path = data.get("folder_path", "").strip()
    sync_interval = data.get("sync_interval", settings.sync_default_interval)
    oauth_token = data.get("oauth_token", "")
    yandex_user = data.get("yandex_user", "")

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not folder_path:
        raise HTTPException(status_code=400, detail="Folder path is required")
    if not folder_path.startswith("/") and not folder_path.startswith("disk:/"):
        folder_path = "/" + folder_path

    source = SyncSource(
        name=name,
        folder_path=folder_path,
        sync_interval=sync_interval,
        status="idle" if oauth_token else "not_connected",
        oauth_token=oauth_token or None,
        yandex_user=yandex_user or None,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    if oauth_token:
        _register_in_scheduler(source)

    logger.info(f"Created sync source '{name}' (id={source.id}, connected={bool(oauth_token)})")
    return _source_to_dict(source)


@router.delete("/sync-sources/{source_id}")
async def delete_sync_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(SyncSource).filter(SyncSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Not found")
    _unregister_from_scheduler(source_id)
    db.delete(source)
    db.commit()
    return {"message": "Deleted"}


@router.post("/sync-sources/{source_id}/sync")
async def trigger_sync(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    source = db.query(SyncSource).filter(SyncSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Not found")
    if not source.oauth_token:
        raise HTTPException(status_code=400, detail="Not connected")
    if source.status == "syncing":
        raise HTTPException(status_code=409, detail="Already syncing")
    background_tasks.add_task(_run_sync_wrapper, source.id)
    return {"message": "Sync started"}


@router.post("/sync-sources/{source_id}/disconnect")
async def disconnect_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(SyncSource).filter(SyncSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Not found")
    source.oauth_token = None
    source.yandex_user = None
    source.status = "not_connected"
    db.commit()
    _unregister_from_scheduler(source_id)
    return {"message": "Disconnected"}


# --- Helpers ---

def _source_to_dict(source: SyncSource) -> dict:
    return {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
        "folder_path": source.folder_path,
        "sync_interval": source.sync_interval,
        "last_synced_at": source.last_synced_at.isoformat() if source.last_synced_at else None,
        "status": source.status,
        "error_message": source.error_message,
        "yandex_user": source.yandex_user,
        "is_connected": bool(source.oauth_token),
        "oauth_token": source.oauth_token,
        "created_at": source.created_at.isoformat() if source.created_at else None,
    }


async def _run_sync_wrapper(source_id: int):
    from app.services.yandex_disk import run_sync
    await run_sync(source_id)


def _register_in_scheduler(source: SyncSource):
    try:
        from app.workers.sync_scheduler import register_source
        register_source(source.id, source.sync_interval)
    except Exception as e:
        logger.warning(f"Could not register source {source.id}: {e}")


def _unregister_from_scheduler(source_id: int):
    try:
        from app.workers.sync_scheduler import unregister_source
        unregister_source(source_id)
    except Exception as e:
        logger.warning(f"Could not unregister source {source_id}: {e}")
