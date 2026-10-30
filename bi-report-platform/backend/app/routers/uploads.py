"""
Pictures people put on reports: a logo in the header, or an image tile on a dashboard.

Uploading needs a signed-in account. Reading does not: a browser can't send a token with an
<img> tag, so the file's address is its own key — a random 32-character name that isn't listed
anywhere. Treat an upload as readable by anyone who has the link, and don't put anything
confidential in one.

Files are served back with the type they were saved as and nothing else: no sniffing, and a
content security policy that stops a page of its own from doing anything, which is what makes an
uploaded SVG safe to open directly as well as to draw in an <img>.
"""

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Upload, User

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# backend/uploads, beside the app package.
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"

MAX_BYTES = 4 * 1024 * 1024  # 4 MB: plenty for a logo, small enough to keep out of the way

# What a picture may be, and the extension it is stored with.
TYPES = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    "image/gif": ".gif", "image/svg+xml": ".svg",
}

# An uploaded file can't load or run anything, wherever it is opened.
SAFE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "public, max-age=31536000, immutable",
}


def _url(stored_name: str) -> str:
    return f"/api/uploads/{stored_name}"


@router.post("", status_code=201)
async def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """Saves one picture and returns the address to put in a report."""
    kind = (file.content_type or "").split(";")[0].strip().lower()
    if kind not in TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"{file.filename or 'That file'} is {kind or 'of an unknown type'}. "
                            "Pictures can be PNG, JPEG, WebP, GIF or SVG.")
    # Read with a cap rather than trusting the declared length.
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"That picture is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is empty.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = secrets.token_urlsafe(24).replace("-", "_") + TYPES[kind]
    (UPLOAD_DIR / stored).write_bytes(content)

    row = Upload(stored_name=stored, original_name=(file.filename or "")[:200], content_type=kind,
                 size_bytes=len(content), owner_id=user.id)
    db.add(row)
    db.commit()
    return {"url": _url(stored), "name": row.original_name, "content_type": kind, "size_bytes": row.size_bytes}


@router.get("/{stored_name}")
def read_image(stored_name: str, db: Session = Depends(get_db)):
    """The picture itself. No sign-in: the random name in the address is what protects it."""
    row = db.scalar(select(Upload).where(Upload.stored_name == stored_name))
    path = UPLOAD_DIR / stored_name
    # resolve() keeps a name like "..%2Fsecret" from reaching outside the folder.
    if row is None or not path.exists() or path.resolve().parent != UPLOAD_DIR.resolve():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That picture isn't here")
    return FileResponse(path, media_type=row.content_type, headers=SAFE_HEADERS)
