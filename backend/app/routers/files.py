from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.storage import resolve

router = APIRouter(tags=["files"])


@router.get("/files/{path:path}")
def get_file(path: str) -> FileResponse:
    found = resolve(path)
    if found is None:
        raise HTTPException(404, "File not found.")
    return FileResponse(found, media_type="image/png" if found.suffix == ".png" else "image/jpeg")
