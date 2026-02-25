"""
APScheduler-based periodic sync scheduler.
Manages interval triggers for each sync source.
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


def init_scheduler():
    """Initialize the APScheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        scheduler.start()
        logger.info("Sync scheduler started")
    return scheduler


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Sync scheduler stopped")
    scheduler = None


def register_source(source_id: int, interval_minutes: int):
    """Register or update a sync job for a source."""
    global scheduler
    if scheduler is None:
        return

    job_id = f"sync_source_{source_id}"

    # Remove existing job if any
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    scheduler.add_job(
        _run_sync_job,
        trigger=IntervalTrigger(minutes=max(interval_minutes, 1)),
        id=job_id,
        args=[source_id],
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled sync source {source_id} every {interval_minutes} min")


def unregister_source(source_id: int):
    """Remove a sync job for a source."""
    global scheduler
    if scheduler is None:
        return

    job_id = f"sync_source_{source_id}"
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)
        logger.info(f"Unregistered sync source {source_id}")


def register_all_sources():
    """Load all sync sources from DB and register them."""
    from app.database import SessionLocal
    from app.models import SyncSource

    db = SessionLocal()
    try:
        sources = db.query(SyncSource).all()
        for source in sources:
            register_source(source.id, source.sync_interval)
        if sources:
            logger.info(f"Registered {len(sources)} sync sources from database")
    except Exception as e:
        logger.warning(f"Failed to register sync sources: {e}")
    finally:
        db.close()


async def _run_sync_job(source_id: int):
    """Job wrapper that runs sync for a given source."""
    from app.services.yandex_disk import run_sync
    try:
        await run_sync(source_id)
    except Exception as e:
        logger.error(f"Scheduled sync for source {source_id} failed: {e}")
