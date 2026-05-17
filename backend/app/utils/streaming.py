"""Streaming helpers for safely serving generated media files.

This module provides a small helper that writes bytes to a temporary file and
returns a FastAPI `StreamingResponse` that streams the file in chunks and
ensures the temporary file is removed after streaming completes.

The implementation is intentionally small and synchronous so it can be used
from FastAPI sync or async routes without introducing blocking I/O in the
request handler (the file is written up-front; streaming uses normal file I/O
in a small chunked iterator).
"""
from __future__ import annotations

import os
import tempfile
from typing import Iterator

from fastapi.responses import StreamingResponse

CHUNK_SIZE = 8192


def stream_temp_file(wav_bytes: bytes, filename: str) -> StreamingResponse:
    """Write bytes to a temp file and stream it safely as a WAV download.

    The returned StreamingResponse will stream the file in CHUNK_SIZE chunks
    and remove the temporary file after the iterator completes.

    Args:
        wav_bytes: Raw WAV bytes to write and stream.
        filename: Suggested filename for the download Content-Disposition.

    Returns:
        A FastAPI StreamingResponse that streams the written file.
    """
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        temp.write(wav_bytes)
        temp.flush()
        temp.close()

        def file_iterator() -> Iterator[bytes]:
            try:
                with open(temp.name, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            finally:
                # Best-effort cleanup; if removal fails, do not raise to avoid
                # breaking the response streaming (log if needed at call site).
                try:
                    os.remove(temp.name)
                except Exception:
                    pass

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(os.path.getsize(temp.name)),
        }

        return StreamingResponse(file_iterator(), media_type="audio/wav", headers=headers)
    except Exception:
        # Ensure temp file is removed on failure to avoid leaking temp files.
        try:
            temp.close()
        except Exception:
            pass
        try:
            os.remove(temp.name)
        except Exception:
            pass
        raise
