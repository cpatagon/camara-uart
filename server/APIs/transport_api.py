#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transport_api.py — API de transporte UART ROBUSTA
- Chunks pequeños con pausas ajustables
- Confirmación al final de transmisión
- Mejor manejo de buffers
"""

import time
import struct
import logging
import serial

START_MARKER = b"\xAA" * 10
END_MARKER   = b"\xBB" * 10
END_TEXT     = b"<FIN_TRANSMISION>\r\n"
SIZE_BYTES   = 4
DEFAULT_CHUNK = 512  # Chunk medio

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
                write_timeout=5,  # timeout más largo para escritura
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )
            
            # Limpieza más agresiva
            for i in range(3):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)
            
            logging.info(f"✅ UART: {self.port} @ {self.baudrate} (rtscts={self.rtscts}, xonxoff={self.xonxoff})")
            return True
        except Exception as e:
            logging.error(f"❌ UART open: {e}")
            return False

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                # Drenar todo antes de cerrar
                self.ser.flush()
                time.sleep(0.1)
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
        Envío ROBUSTO por tamaño exacto con pausas adaptativas
        """
        if not self.ser or not self.ser.is_open:
            logging.error("❌ UART no abierta")
            return False

        size = len(data)
        
        # Calcular pausa adaptativa basada en tamaño
        if size > 200000:  # >200KB
            adaptive_sleep = max(0.005, inter_chunk_sleep_ms / 1000.0)
            chunk_size = min(chunk_size, 256)  # chunks más pequeños
        elif size > 100000:  # >100KB  
            adaptive_sleep = max(0.003, inter_chunk_sleep_ms / 1000.0)
            chunk_size = min(chunk_size, 512)
        else:
            adaptive_sleep = max(0.001, inter_chunk_sleep_ms / 1000.0)
        
        logging.info(f"📊 Enviando {size} bytes (chunks={chunk_size}, sleep={adaptive_sleep*1000:.1f}ms)...")

        try:
            # 1. Preámbulo con confirmación
            self.ser.write(START_MARKER)
            self.ser.flush()
            time.sleep(0.02)  # pausa después del marcador
            
            size_bytes = struct.pack(">I", size)
            self.ser.write(size_bytes)
            self.ser.flush()
            time.sleep(0.02)  # pausa después del tamaño
            
            # 2. Envío por chunks con control estricto
            sent = 0
            view = memoryview(data)
            last_log = 0
            
            while sent < size:
                # Calcular chunk actual
                remaining = size - sent
                current_chunk_size = min(chunk_size, remaining)
                chunk = view[sent:sent + current_chunk_size]
                
                # Envío con verificación
                bytes_written = self.ser.write(chunk)
                if bytes_written != len(chunk):
                    logging.warning(f"⚠️ Escritura parcial: {bytes_written}/{len(chunk)}")
                
                self.ser.flush()  # Forzar envío inmediato
                sent += bytes_written
                
                # Pausa adaptativa
                if adaptive_sleep > 0:
                    time.sleep(adaptive_sleep)
                
                # Log de progreso
                pct = int(sent * 100 / size) if size else 100
                if pct - last_log >= 10:
                    logging.info(f"📦 Progreso: {sent}/{size} bytes ({pct}%)")
                    last_log = pct
            
            # 3. Confirmación final CRÍTICA
            self.ser.flush()
            time.sleep(0.1)  # Pausa larga para estabilizar
            
            # Verificar que no hay datos pendientes en el buffer de salida
            start_wait = time.time()
            while self.ser.out_waiting > 0 and (time.time() - start_wait) < 5:
                logging.info(f"⏳ Esperando buffer salida: {self.ser.out_waiting} bytes")
                time.sleep(0.1)
                self.ser.flush()
            
            logging.info("✅ Envío completo - datos confirmados")
            
            # 4. Marcadores finales (opcionales)
            if send_end_markers:
                time.sleep(0.05)
                self.ser.write(END_MARKER)
                self.ser.flush()
                time.sleep(0.02)
                
                self.ser.write(END_TEXT)
                self.ser.flush()
                time.sleep(0.02)
                
                logging.info("🏁 Marcadores finales enviados")
            
            return sent == size
            
        except Exception as e:
            logging.error(f"❌ Error durante envío: {e}")
            return False

    def send_file(self, path: str, **kwargs) -> bool:
        with open(path, "rb") as f:
            data = f.read()
        return self.send_bytes(data, **kwargs)
