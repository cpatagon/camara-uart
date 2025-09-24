#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transport_api.py — API de transporte UART
- Envío por TAMAÑO EXACTO (preamble + 4B big-endian + bytes)
- FIN opcional (binario/texto) para debug humano
"""

import time
import struct
import logging
import serial

START_MARKER = b"\xAA" * 10
END_MARKER   = b"\xBB" * 10       # opcional
END_TEXT     = b"<FIN_TRANSMISION>\r\n"  # opcional
SIZE_BYTES   = 4
DEFAULT_CHUNK = 1024

class UartTransport:
    def __init__(self, port: str, baudrate: int = 57600, timeout: float = 1.0,
                 rtscts: bool = False, xonxoff: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.rtscts = rtscts
        self.xonxoff = xonxoff
        self.ser: serial.Serial | None = None

    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout,
                write_timeout=3,
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )
            # limpieza
            for _ in range(2):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.05)
            logging.info(f"✅ UART: {self.port} @ {self.baudrate} (rtscts={self.rtscts}, xonxoff={self.xonxoff})")
            return True
        except Exception as e:
            logging.error(f"❌ UART open: {e}")
            return False

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.reset_output_buffer()
                self.ser.reset_input_buffer()
                self.ser.close()
                logging.info("🔌 UART cerrada")
        except:
            pass

    def send_bytes(self, data: bytes,
                   chunk_size: int = DEFAULT_CHUNK,
                   inter_chunk_sleep_ms: int = 0,
                   send_end_markers: bool = True) -> bool:
        """
        Envío por tamaño exacto: START_MARKER + 4B + data [+ FIN opcional]
        """
        if not self.ser or not self.ser.is_open:
            logging.error("❌ UART no abierta")
            return False

        size = len(data)
        logging.info(f"📊 Enviando {size} bytes...")

        # preámbulo
        self.ser.write(START_MARKER)
        self.ser.write(struct.pack(">I", size))
        self.ser.flush()

        # bucle envío
        sent = 0
        view = memoryview(data)
        last_log = 0
        sleep_s = max(0, inter_chunk_sleep_ms) / 1000.0

        while sent < size:
            n = self.ser.write(view[sent:sent + chunk_size])
            if not n:
                n = 0
            sent += n

            if sleep_s > 0:
                time.sleep(sleep_s)

            pct = int(sent * 100 / size) if size else 100
            if pct - last_log >= 10:
                logging.info(f"📦 Progreso: {sent}/{size} bytes ({pct}%)")
                last_log = pct

        # drenar
        self.ser.flush()
        logging.info("✅ Envío completo")

        # FIN opcional (para debug humano; el cliente 4.1 lo ignora)
        if send_end_markers:
            self.ser.write(END_MARKER)
            self.ser.write(END_TEXT)
            self.ser.flush()
            logging.info("🏁 FIN transmitido")

        return sent == size

    def send_file(self, path: str, **kwargs) -> bool:
        with open(path, "rb") as f:
            data = f.read()
        return self.send_bytes(data, **kwargs)
