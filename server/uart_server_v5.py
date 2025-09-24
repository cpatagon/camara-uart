#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uart_server_v5.py — Servidor que compone photo_api + transport_api
"""

import argparse
import logging
import os, sys
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "APIs"))

from photo_api import capture_photo, capture_to_file
from transport_api import UartTransport

# Log
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# Comandos
RE_FOTO      = re.compile(r"^<FOTO:\{size_name:(\w+)\}>$")
RE_CAPTURAR  = re.compile(r"^<CAPTURAR:\{size_name:(\w+)\}>$")
RE_ENVIAR    = re.compile(r"^<ENVIAR:\{path:([^}]+)\}>$")

RESP_OK  = "OK|"
RESP_BAD = "BAD|"

DEFAULT_LAST = "/tmp/last.jpg"

def parse_command(line: str):
    line = line.strip()
    m = RE_FOTO.match(line)
    if m: return ("FOTO", m.group(1))
    m = RE_CAPTURAR.match(line)
    if m: return ("CAPTURAR", m.group(1))
    m = RE_ENVIAR.match(line)
    if m: return ("ENVIAR", m.group(1))
    return (None, None)

def serve(port: str, baud: int, rtscts: bool, xonxoff: bool,
          use_camera: bool, fallback_image: str | None,
          inter_chunk_sleep_ms: int):
    uart = UartTransport(port, baudrate=baud, rtscts=rtscts, xonxoff=xonxoff)
    if not uart.connect():
        return

    try:
        ser = uart.ser  # acceso crudo para leer comandos
        assert ser is not None

        logging.info("🟢 Esperando comandos...")
        while True:
            # leemos por línea (comandos terminan con CR/LF)
            line = ser.readline().decode("utf-8", errors="ignore")
            if not line:
                continue

            cmd, arg = parse_command(line)
            if not cmd:
                logging.debug(f"(ruido) {line.strip()!r}")
                continue

            if cmd == "CAPTURAR":
                logging.info(f"🎯 CAPTURAR {arg}")
                if capture_to_file(DEFAULT_LAST, size_name=arg, use_camera=use_camera,
                                   fallback_image=fallback_image, timeout_s=8):
                    size = os.path.getsize(DEFAULT_LAST)
                    ser.write(f"{RESP_OK}{size}\r\n".encode("utf-8"))
                    ser.flush()
                else:
                    ser.write(f"{RESP_BAD}NO_IMAGE\r\n".encode("utf-8"))
                    ser.flush()

            elif cmd == "ENVIAR":
                path = DEFAULT_LAST if arg == "LAST" else arg
                if not os.path.isfile(path):
                    ser.write(f"{RESP_BAD}NO_FILE\r\n".encode("utf-8"))
                    ser.flush()
                    continue
                size = os.path.getsize(path)
                ser.write(f"{RESP_OK}{size}\r\n".encode("utf-8"))
                ser.flush()
                ok = uart.send_file(path, inter_chunk_sleep_ms=inter_chunk_sleep_ms, send_end_markers=True)
                if ok:
                    logging.info("🎉 ENVIAR OK")
                else:
                    logging.error("❌ ENVIAR fallo")

            elif cmd == "FOTO":
                logging.info(f"📸 FOTO {arg} (capturar+enviar)")
                data = capture_photo(arg, use_camera=use_camera, fallback_image=fallback_image, timeout_s=8)
                if not data:
                    ser.write(f"{RESP_BAD}NO_IMAGE\r\n".encode("utf-8"))
                    ser.flush()
                    continue
                # respuesta OK|size y envío
                ser.write(f"{RESP_OK}{len(data)}\r\n".encode("utf-8"))
                ser.flush()
                ok = uart.send_bytes(data, inter_chunk_sleep_ms=inter_chunk_sleep_ms, send_end_markers=True)
                if ok:
                    # actualizar last
                    try:
                        with open(DEFAULT_LAST, "wb") as f:
                            f.write(data)
                    except:
                        pass
                    logging.info("🎉 FOTO OK")
                else:
                    logging.error("❌ FOTO fallo")
    except KeyboardInterrupt:
        logging.info("🛑 Detenido por usuario")
    finally:
        uart.close()

def main():
    ap = argparse.ArgumentParser(description="Servidor UART v5 (APIs separadas: captura y transporte)")
    ap.add_argument("port")
    ap.add_argument("-b", "--baud", type=int, default=57600)
    ap.add_argument("--rtscts", action="store_true")
    ap.add_argument("--xonxoff", action="store_true")
    ap.add_argument("--no-camera", dest="use_camera", action="store_false")
    ap.add_argument("--fallback-image")
    ap.add_argument("--sleep-ms", type=int, default=0, help="Pausa entre chunks (ms)")
    args = ap.parse_args()

    serve(args.port, args.baud, args.rtscts, args.xonxoff,
          args.use_camera, args.fallback_image, args.sleep_ms)

if __name__ == "__main__":
    main()
