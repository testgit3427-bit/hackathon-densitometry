import os
import re
import time
from pathlib import Path

import requests
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import dcm_processing as dcm
import zones

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "medgemma1.5:4b")
MAX_FILE_BYTES = 50 * 1024 * 1024
ENABLE_AUDIT = os.getenv("DXA_ENABLE_AUDIT", "0") == "1"

app = FastAPI(title="DXA Quality Control Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_name(filename):
    if not filename:
        return "scan.dcm"
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", name).strip()
    return name or "scan.dcm"


def _assert_within_project(path):
    resolved = Path(path).resolve()
    root = PROJECT_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise PermissionError(f"Путь вне корня проекта: {resolved}")
    return resolved


def _audit(event, data=None):
    if not ENABLE_AUDIT:
        return
    import json
    import logging

    log_dir = _assert_within_project(PROJECT_ROOT / "backend" / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    line = {"ts": time.time(), "event": event, **(data or {})}
    try:
        with open(log_dir / "audit.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception as exc:
        logging.getLogger("uvicorn.error").warning("audit write failed: %s", exc)


def _ollama_models():
    try:
        response = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=(5, 15))
        response.raise_for_status()
        return [item.get("name", "") for item in response.json().get("models", [])]
    except requests.RequestException:
        return None


def _ask_medgemma(prompt, image_base64):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 1024, "num_ctx": 4096},
    }
    try:
        response = requests.post(
            f"{OLLAMA_BASE}/api/generate", json=payload, timeout=(15, 1200)
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Ollama недоступен: {exc}") from exc
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama вернул {response.status_code}: {response.text[:300]}",
        )
    data = response.json()
    reply = (data.get("response") or "").strip()
    if not reply and data.get("error"):
        raise HTTPException(status_code=502, detail=f"Ollama: {data['error']}")
    return reply


def _decide(reply):
    text = _clean_model_reply(reply)
    matches = list(re.finditer(r"\b(ACCEPTED|REJECTED)\b", text, re.IGNORECASE))
    if matches:
        return matches[-1].group(1).upper()
    # Fallback: ищем DECISION: ACCEPTED/REJECTED
    decision_match = re.search(r"DECISION:\s*(ACCEPTED|REJECTED)", text, re.IGNORECASE)
    if decision_match:
        return decision_match.group(1).upper()
    # Fallback: ищем русские аналоги
    if re.search(r"\b(ПРИНЯТ|ПРИНЯТА|ПРИНЯТО|КОРРЕКТЕН|ДОПУСТИМ)\b", text, re.IGNORECASE):
        return "ACCEPTED"
    if re.search(r"\b(ОТКЛОНЁН|ОТКЛОНЕН|ОШИБКА|БРАК|НЕКОРРЕКТЕН|НЕДОПУСТИМ)\b", text, re.IGNORECASE):
        return "REJECTED"
    return "UNKNOWN"


_THOUGHT_BLOCK_RE = re.compile(r"<unused\d+>.*?<unused\d+>", re.DOTALL)
_STRAY_TAG_RE = re.compile(r"</?unused\d+>\s*", re.IGNORECASE)


def _clean_model_reply(reply):
    text = _THOUGHT_BLOCK_RE.sub("", reply or "")
    text = _STRAY_TAG_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


@app.get("/")
def root():
    return {
        "service": "DXA Quality Control Assistant",
        "version": app.version,
        "ollama_model": OLLAMA_MODEL,
    }


@app.get("/health")
def health():
    models = _ollama_models()
    reachable = models is not None
    requested_available = False
    if models:
        requested_available = any(
            model == OLLAMA_MODEL or model.split(":")[0] == OLLAMA_MODEL
            for model in models
        )
    return {
        "status": "ok",
        "ollama": {
            "base_url": OLLAMA_BASE,
            "reachable": reachable,
            "requested_model": OLLAMA_MODEL,
            "requested_model_available": requested_available,
            "models": models or [],
        },
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), zone: str = Form(default="")):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Получен пустой файл.")
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Файл превышает 50 МБ.")

    safe_name = _safe_name(file.filename)
    _audit("upload", {"file": safe_name, "bytes": len(raw)})

    try:
        ds = dcm.decode_dicom(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if "PixelData" not in ds:
        raise HTTPException(status_code=422, detail="В DICOM-файле отсутствуют данные пикселей (PixelData).")

    meta = dcm.extract_metadata(ds)

    try:
        preview_image = dcm.dataset_to_preview_image(ds, include_overlays=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    preview_base64 = dcm.image_to_base64(preview_image)

    zone_key = zones.detect_zone(meta)
    if zone and zone in zones.ZONE_GUIDELINES:
        zone_key = zone

    prompt = zones.build_prompt(zone_key, meta)
    try:
        reply = _ask_medgemma(prompt, preview_base64)
    except HTTPException as exc:
        _audit("ollama_error", {"file": safe_name, "detail": str(exc.detail)})
        raise
    clean_reply = _clean_model_reply(reply)
    if not clean_reply:
        raise HTTPException(status_code=502, detail="MedGemma не вернул текст ответа.")

    decision = _decide(clean_reply)
    _audit("analysis", {"file": safe_name, "zone": zone_key, "decision": decision})

    return {
        "decision": decision,
        "response": clean_reply,
        "prompt": prompt,
        "zone": zone_key,
        "zone_label": zones.zone_label(zone_key),
        "ollama_model": OLLAMA_MODEL,
        "metadata": meta,
        "preview_base64": preview_base64,
    }