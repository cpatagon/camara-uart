#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uart_server_robust.py — Servidor robusto con protocolo ACK
Usa transport_api_robust.py para eliminación del problema de chunks de 110ms
"""

import argparse
import logging
import os, sys
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "APIs"))

from photo_api import capture_photo, capture_to_file
from transport_api_robust import UartTransportRobust

# Log
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# Comandos (igual que antes)
RE_FOTO      = re.compile(r"^<FOTO:\{size_name:(\w+)\}>$")
RE_CAPTURAR  = re.compile(r"^<CAPTURAR:\{size_name:(\w+)\}>$")
RE_ENVIAR    = re.compile(r"^<ENVIAR:\{path:([^}]+)\}>$")

RESP_OK  = "OK|"
RESP_BAD = "BAD|"

DEFAULT_LAST = "/tmp/last.jpg"

def parse_command(line: str):
    """Parseo de comandos (sin cambios)"""
    line = line.strip()
    m = RE_FOTO.match(line)
    if m: return ("FOTO", m.group(1))
    m = RE_CAPTURAR.match(line)
    if m: return ("CAPTURAR", m.group(1))
    m = RE_ENVIAR.match(line)
    if m: return ("ENVIAR", m.group(1))
    return (None, None)

def serve_robust(port: str, baud: int, rtscts: bool, xonxoff: bool,
                use_camera: bool, fallback_image: str | None,
                inter_chunk_sleep_ms: int):
    """Servidor robusto con protocolo ACK"""
    
    # CAMBIO PRINCIPAL: Usar UartTransportRobust en lugar de UartTransport
    uart = UartTransportRobust(port,
                              baudrate=baud,
                              rtscts=rtscts,
                              xonxoff=xonxoff)
    if not uart.connect():
        return

    try:
        ser = uart.ser  # acceso crudo para leer comandos
        assert ser is not None

        logging.info("🟢 Servidor ROBUSTO esperando comandos...")
        while True:
            # Leer comandos línea por línea
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
                    logging.info(f"✅ CAPTURAR exitoso: {size} bytes guardados")
                else:
                    ser.write(f"{RESP_BAD}NO_IMAGE\r\n".encode("utf-8"))
                    ser.flush()
                    logging.error("❌ CAPTURAR falló")

            elif cmd == "ENVIAR":
                path = DEFAULT_LAST if arg == "LAST" else arg
                if not os.path.isfile(path):
                    ser.write(f"{RESP_BAD}NO_FILE\r\n".encode("utf-8"))
                    ser.flush()
                    logging.error(f"❌ ENVIAR: archivo no existe: {path}")
                    continue
                    
                size = os.path.getsize(path)
                ser.write(f"{RESP_OK}{size}\r\n".encode("utf-8"))
                ser.flush()
                logging.info(f"📤 ENVIAR iniciado: {path} ({size} bytes)")
                
                # CAMBIO: Usar el método robusto
                ok = uart.send_bytes_robust(
                    open(path, 'rb').read(),
                    inter_chunk_sleep_ms=inter_chunk_sleep_ms,
                    max_retries=2,
                    wait_client_ready=True
                )
                
                if ok:
                    logging.info("🎉 ENVIAR ROBUSTO completado exitosamente")
                else:
                    logging.error("❌ ENVIAR ROBUSTO falló")

            elif cmd == "FOTO":
                logging.info(f"📸 FOTO {arg} (capturar+enviar robusto)")
                data = capture_photo(arg, use_camera=use_camera, fallback_image=fallback_image, timeout_s=8)
                if not data:
                    ser.write(f"{RESP_BAD}NO_IMAGE\r\n".encode("utf-8"))
                    ser.flush()
                    logging.error("❌ FOTO: no se pudo capturar imagen")
                    continue
                
                # Respuesta OK|size
                ser.write(f"{RESP_OK}{len(data)}\r\n".encode("utf-8"))
                ser.flush()
                logging.info(f"📤 FOTO iniciado: captura de {len(data)} bytes")
                
                # CAMBIO: Usar envío robusto
                ok = uart.send_bytes_robust(
                    data, 
                    inter_chunk_sleep_ms=inter_chunk_sleep_ms,
                    max_retries=2,
                    wait_client_ready=True
                )
                
                if ok:
                    # Guardar como última imagen (para comando ENVIAR posterior)
                    try:
                        with open(DEFAULT_LAST, "wb") as f:
                            f.write(data)
                        logging.debug(f"💾 Imagen guardada como última: {DEFAULT_LAST}")
                    except Exception as e:
                        logging.warning(f"⚠️ No se pudo guardar como última: {e}")
                    
                    logging.info("🎉 FOTO ROBUSTA completada exitosamente")
                else:
                    logging.error("❌ FOTO ROBUSTA falló")
                    
    except KeyboardInterrupt:
        logging.info("🛑 Servidor robusto detenido por usuario")
    finally:
        uart.close()

def main():
    ap = argparse.ArgumentParser(description="Servidor UART Robusto con protocolo ACK")
    ap.add_argument("port")
    ap.add_argument("-b", "--baud", type=int, default=57600)
    ap.add_argument("--rtscts", action="store_true")
    ap.add_argument("--xonxoff", action="store_true")
    ap.add_argument("--no-camera", dest="use_camera", action="store_false")
    ap.add_argument("--fallback-image")
    ap.add_argument("--sleep-ms", type=int, default=1, 
                    help="Pausa entre chunks (ms) - con protocolo robusto es menos crítico")
    args = ap.parse_args()

    print("=" * 70)
    print("🚀 SERVIDOR UART ROBUSTO con eliminación de chunks problemáticos")
    print("=" * 70)
    print(f"Puerto: {args.port} @ {args.baud} baud")
    print(f"Flow control: RTS/CTS={args.rtscts}, XON/XOFF={args.xonxoff}")
    print(f"Cámara: {'SÍ' if args.use_camera else 'NO'}")
    print(f"Fallback: {args.fallback_image or 'Ninguno'}")
    print(f"Sleep entre chunks: {args.sleep_ms}ms")
    print("=" * 70)

    serve_robust(args.port, args.baud, args.rtscts, args.xonxoff,
                args.use_camera, args.fallback_image, args.sleep_ms)

if __name__ == "__main__":
    main()
