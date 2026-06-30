"""FastAPI app: REST API + static frontend, all on localhost."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pipeline
from .models import JobState
from .renderer import list_styles
from .store import store
from .zotero import ZoteroError, client

app = FastAPI(title="Auto Bibliography Generator")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# --------------------------------------------------------------------------
# Zotero / styles
# --------------------------------------------------------------------------
@app.get("/api/zotero/status")
def zotero_status():
    return client.status()


@app.get("/api/zotero/collections")
def zotero_collections():
    try:
        return {"collections": client.collections()}
    except ZoteroError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/styles")
def styles():
    return {"styles": list_styles()}


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------
@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    style: str = Form("apa"),
    collection: Optional[str] = Form(None),
    library_file: Optional[UploadFile] = File(None),
):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Please upload a .docx file.")

    job = store.create(style=style, collection=collection or None)
    job_dir = store.job_dir(job.id)
    input_path = job_dir / "input.docx"
    input_path.write_bytes(await file.read())
    job.input_path = str(input_path)
    job.output_path = str(job_dir / "result.docx")

    # Resolve the library: uploaded CSL-JSON fallback wins if provided.
    try:
        if library_file is not None:
            lib_path = job_dir / "library.json"
            lib_path.write_bytes(await library_file.read())
            items = client.load_csljson_file(lib_path)
        else:
            items = client.fetch_library(job.collection)
    except ZoteroError as e:
        job.state = JobState.ERROR
        job.error = str(e)
        raise HTTPException(status_code=502,
                            detail=f"Could not load Zotero library: {e}")

    try:
        pipeline.run_parse_and_match(job, items)
    except Exception as e:  # pragma: no cover - defensive
        job.state = JobState.ERROR
        job.error = str(e)
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    return job.to_dict()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_dict()


class Resolutions(BaseModel):
    resolutions: dict[str, Optional[str]]


@app.post("/api/jobs/{job_id}/resolutions")
def post_resolutions(job_id: str, body: Resolutions):
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    pipeline.apply_resolutions(job, body.resolutions)
    return job.to_dict()


@app.post("/api/jobs/{job_id}/generate")
def post_generate(job_id: str):
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    try:
        stats = pipeline.generate(job)
    except Exception as e:  # pragma: no cover - defensive
        job.state = JobState.ERROR
        job.error = str(e)
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
    return {"job": job.to_dict(), "stats": stats}


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    job = store.get(job_id)
    if job is None or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(status_code=404, detail="No generated file yet.")
    return FileResponse(
        job.output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="bibliography.docx",
    )


# --------------------------------------------------------------------------
# Frontend (mounted last so /api/* takes precedence)
# --------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
