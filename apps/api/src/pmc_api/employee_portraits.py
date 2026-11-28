from __future__ import annotations

from asyncio import Semaphore
from io import BytesIO

from fastapi import HTTPException, Request
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from pmc_api.antivirus import ScanUnavailable, ScanVerdict, scan

MAX_UPLOAD_BYTES = 2_000_000
MAX_PORTRAIT_BYTES = 400_000
_slots = Semaphore(4)
_formats = {"image/jpeg": ("JPEG", b"\xff\xd8\xff"), "image/png": ("PNG", b"\x89PNG\r\n\x1a\n")}


def _normalize(payload: bytes, format_name: str) -> bytes:
    try:
        with Image.open(BytesIO(payload), formats=[format_name]) as image:
            width, height = image.size
            if min(width, height) < 64 or max(width, height) > 4096:
                raise HTTPException(422, "portrait dimensions must be between 64 and 4096 pixels")
            if getattr(image, "n_frames", 1) != 1:
                raise HTTPException(415, "animated portraits are not supported")
            image.thumbnail((640, 640))
            pixels = ImageOps.exif_transpose(image).convert("RGBA")
            # Create an independent image with no source metadata or appended bytes.
            portrait = Image.new("RGB", pixels.size, "white")
            portrait.paste(pixels, mask=pixels.getchannel("A"))
            output = BytesIO()
            portrait.save(output, format="JPEG", quality=82)
            normalized = output.getvalue()
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as error:
        raise HTTPException(415, "file is not a supported JPEG or PNG portrait") from error
    if len(normalized) > MAX_PORTRAIT_BYTES:
        raise HTTPException(422, "portrait could not be reduced to the supported size")
    return normalized


def _scan_and_normalize(payload: bytes, format_name: str) -> bytes:
    try:
        verdict = scan(BytesIO(payload))
    except ScanUnavailable as error:
        raise HTTPException(503, "portrait security scan unavailable; retry upload") from error
    if verdict != ScanVerdict.CLEAN:
        raise HTTPException(422, "portrait did not pass security validation")
    return _normalize(payload, format_name)


async def receive_portrait(request: Request) -> bytes:
    media_type = request.headers.get("content-type", "").split(";")[0].lower()
    if media_type not in _formats:
        raise HTTPException(415, "choose a JPEG or PNG portrait")
    format_name, signature = _formats[media_type]
    if _slots.locked():
        raise HTTPException(503, "portrait upload capacity is temporarily full")
    async with _slots:
        payload = bytearray()
        async for chunk in request.stream():
            if len(payload) + len(chunk) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "portrait exceeds 2 MB")
            payload.extend(chunk)
        if not payload.startswith(signature):
            raise HTTPException(415, "file does not match the selected portrait format")
        return await run_in_threadpool(_scan_and_normalize, bytes(payload), format_name)
