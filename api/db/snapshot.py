"""Shared logic for downloading a SQLite snapshot from production.

Used by:
- POST /api/admin/db-import (on-demand admin trigger)
- Startup auto-seed (when staging volume is empty)

The SQLite magic string is validated before the backup file is moved into place.
"""

import shutil
import tempfile
from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger(__name__)

_SQLITE_MAGIC = b"SQLite format 3\x00"
_TIMEOUT_SECS = 60.0


async def download_prod_snapshot(prod_url: str, api_key: str, db_path: str) -> bool:
    """Download a SQLite backup from prod and atomically replace db_path.

    Args:
        prod_url: Base URL of the production API (e.g. https://prod.up.railway.app).
        api_key:  Shared secret for the X-API-Key header.
        db_path:  Destination path where the DB should be written.

    Returns:
        True on success, False on any failure (caller should log before returning False).
    """
    export_url = f"{prod_url.rstrip('/')}/api/admin/db-export"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECS) as client:
            async with client.stream("GET", export_url, headers={"X-API-Key": api_key}) as resp:
                if resp.status_code != 200:
                    logger.error(
                        "Snapshot download: unexpected status",
                        status=resp.status_code,
                        url=export_url,
                    )
                    return False

                first_chunk = True
                with open(tmp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(65536):
                        if first_chunk:
                            if not chunk.startswith(_SQLITE_MAGIC):
                                logger.error(
                                    "Snapshot download: response is not a SQLite file",
                                    magic=chunk[:16].hex(),
                                )
                                return False
                            first_chunk = False
                        f.write(chunk)

    except httpx.TimeoutException as exc:
        logger.error("Snapshot download: timeout", url=export_url, error=str(exc))
        raise  # caller distinguishes 502 vs 400
    except Exception as exc:
        logger.error("Snapshot download: failed", url=export_url, error=str(exc))
        return False
    finally:
        import os

        try:
            os.close(tmp_fd)
        except OSError:
            pass

    # Atomic replace: shutil.move is atomic when src and dst are on the same filesystem
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(tmp_path, db_path)
    logger.info("Snapshot download: success", db_path=db_path, url=export_url)
    return True
