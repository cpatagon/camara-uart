#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uart_server_v5.py — Servidor con verificación ACK final
"""

import argparse
import logging
import os, sys
import re
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "APIs"))

from photo_api import capture_photo, capture_to_file
from transport_api_ack import UartTransport

# Log
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# Comandos
RE_FOTO      = re.compile(r"^<FOTO:\{size_name:(\w+)\}>$")
RE_CAPTURAR  = re.compile(r"^<CAPTURAR:\{size_name:(\w+)\}>$")
RE_ENVIAR    = re.compile(r"^<ENVIAR:\{path:([^}]+)\}>$")

RESP_OK  = "OK|"
RESP_BAD = "BAD|"
ACK_OK   = "ACK_OK"
ACK_MISSING = "ACK_MISSING:"

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

def wait_for_ack(ser, expected_size, timeout=30):
    """Esperar confirmación del cliente y manejar retransmisión"""
    logging.info("📋 Esperando confirmación del cliente...")
    deadline = time.time() + timeout
    
    while time.time() < deadline:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
                
            logging.info(f"📨 Cliente responde: {line}")
            
            if line == ACK_OK:
                logging.info("✅ Cliente confirmó recepción completa")
                return True, 0
            elif line.startswith(ACK_MISSING):
                # Cliente reporta bytes faltantes: ACK_MISSING:1234
                try:
                    received = int(line.split(":")[1])
                    missing = expected_size - received
                    logging.warning(f"⚠️ Cliente reporta {missing} bytes faltantes")
                    return False, missing
                except:
                    logging.error("❌ Formato ACK_MISSING inválido")
                    return False, 0
        except Exception as e:
            logging.debug(f"Error leyendo ACK: {e}")
            
        time.sleep(0.1)
    
    logging.warning("⏰ Timeout esperando ACK del cliente")
    return False, 0

def serve(port: str, baud: int, rtscts: bool, xonxoff: bool,
          use_camera: bool, fallback_image: str | None,
          inter_chunk_sleep_ms: int):
    uart = UartTransport(port,
                         baudrate=baud,
                         rtscts=rtscts,
                         xonxoff=xonxoff)
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
                
                # Envío con verificación ACK
                ok = uart.send_file_with_ack(path, size, inter_chunk_sleep_ms=inter_chunk_sleep_ms)
                if ok:
                    logging.info("🎉 ENVIAR OK verificado")
                else:
                    logging.error("❌ ENVIAR falló verificación")

            elif cmd == "FOTO":
                logging.info(f"📸 FOTO {arg} (capturar+enviar)")
                data = capture_photo(arg, use_camera=use_camera, fallback_image=fallback_image, timeout_s=8)
                if not data:
                    ser.write(f"{RESP_BAD}NO_IMAGE\r\n".encode("utf-8"))
                    ser.flush()
                    continue
                    
                # respuesta OK|size
                ser.write(f"{RESP_OK}{len(data)}\r\n".encode("utf-8"))
                ser.flush()
                
                # Envío con verificación ACK
                ok = uart.send_bytes_with_ack(data, len(data), inter_chunk_sleep_ms=inter_chunk_sleep_ms)
                if ok:
                    # actualizar last
                    try:
                        with open(DEFAULT_LAST, "wb") as f:
                            f.write(data)
                    except:
                        pass
                    logging.info("🎉 FOTO OK verificado")
                else:
                    logging.error("❌ FOTO falló verificación")
                    
    except KeyboardInterrupt:
        logging.info("🛑 Detenido por usuario")
    finally:
        uart.close()

def main():
    ap = argparse.ArgumentParser(description="Servidor UART v5 con verificación ACK")
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
