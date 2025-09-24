#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
photo_api.py — API de captura
- Captura con rpicam-still (opcional)
- Soporta fallback desde archivo
- Retorna bytes o guarda a archivo
"""

import os
import subprocess
import logging

RESOLUTIONS = {
    "THUMBNAIL": (320, 240),
    "LOW_LIGHT": (640, 480),
    "HD_READY":  (1280, 720),
    "FULL_HD":   (1920, 1080),
    "ULTRA_WIDE": (4056, 3040),
}

def _capture_with_rpicam(size_name: str, timeout_s: int = 8) -> bytes | None:
    w, h = RESOLUTIONS.get(size_name.upper(), RESOLUTIONS["THUMBNAIL"])
    cmd = ["rpicam-still", "-n", "-t", "1", "--width", str(w), "--height", str(h), "-o", "-"]
    logging.info(f"📷 rpicam-still {w}x{h} (timeout {timeout_s}s)")
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        logging.warning(f"⚠️ rpicam-still rc={proc.returncode}, stderr={proc.stderr[:120]!r}")
        return None
    except subprocess.TimeoutExpired:
        logging.warning("⚠️ rpicam-still: timeout")
        return None
    except Exception as e:
        logging.warning(f"⚠️ rpicam-still error: {e}")
        return None

def _load_fallback(fallback_image: str | None) -> bytes | None:
    if fallback_image and os.path.isfile(fallback_image):
        with open(fallback_image, "rb") as f:
            return f.read()
    return None

def capture_photo(size_name: str = "THUMBNAIL",
                  use_camera: bool = True,
                  fallback_image: str | None = None,
                  timeout_s: int = 8) -> bytes | None:
    """
    Devuelve bytes JPEG o None si falla todo.
    """
    data = None
    if use_camera:
        data = _capture_with_rpicam(size_name, timeout_s)
    if data is None:
        data = _load_fallback(fallback_image)
    if data is None:
        logging.error("❌ No hay imagen (ni cámara ni fallback)")
    return data

def capture_to_file(out_path: str,
                    size_name: str = "THUMBNAIL",
                    use_camera: bool = True,
                    fallback_image: str | None = None,
                    timeout_s: int = 8) -> bool:
    """
    Guarda JPEG en 'out_path'. Retorna True/False.
    """
    data = capture_photo(size_name, use_camera, fallback_image, timeout_s)
    if not data:
        return False
    with open(out_path, "wb") as f:
        f.write(data)
    logging.info(f"💾 Imagen guardada en {out_path} ({len(data)} bytes)")
    return True
