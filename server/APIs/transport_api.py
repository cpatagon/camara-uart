#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transport_api.py — API de transporte UART CORREGIDA
- Verificación estricta del envío final
- Manejo robusto de buffers
- Timeout extendido para writes
"""

import time
import struct
import logging
import serial

START_MARKER = b"\xAA" * 10
END_MARKER   = b"\xBB" * 10
END_TEXT     = b"<FIN_TRANSMISION>\r\n"
SIZE_BYTES   = 4
DEFAULT_CHUNK = 256  # Chunks pequeños para estabilidad

class UartTransport:
    def __init__(self, port: str, baudrate: int = 57600, timeout: float = 2.0,
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
                write_timeout=15,  # TIMEOUT LARGO para escritura
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )
            
            # Limpieza robusta
            for _ in range(3):
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
                # Drenaje final antes de cerrar
                self.ser.flush()
                timeout_start = time.time()
                while self.ser.out_waiting > 0 and (time.time() - timeout_start) < 10:
                    time.sleep(0.1)
                
                self.ser.reset_output_buffer()
                self.ser.reset_input_buffer()
                self.ser.close()
                logging.info("🔌 UART cerrada")
        except Exception as e:
            logging.debug(f"Error cerrando UART: {e}")

    def send_bytes(self, data: bytes,
                   chunk_size: int = DEFAULT_CHUNK,
                   inter_chunk_sleep_ms: int = 0,
                   send_end_markers: bool = True) -> bool:
        """
        Envío ULTRA-ROBUSTO con verificación final completa
        """
        if not self.ser or not self.ser.is_open:
            logging.error("❌ UART no abierta")
            return False

        size = len(data)
        
        # Ajuste dinámico de parámetros según tamaño
        if size > 200000:
            chunk_size = min(chunk_size, 128)
            base_sleep = max(0.008, inter_chunk_sleep_ms / 1000.0)
        elif size > 100000:
            chunk_size = min(chunk_size, 256)
            base_sleep = max(0.005, inter_chunk_sleep_ms / 1000.0)
        else:
            base_sleep = max(0.003, inter_chunk_sleep_ms / 1000.0)
        
        logging.info(f"📊 Enviando {size} bytes (chunks={chunk_size}, sleep={base_sleep*1000:.1f}ms)...")

        try:
            # 1. Preámbulo con confirmación
            self._send_with_verification(START_MARKER, "marcador inicio")
            time.sleep(0.05)
            
            size_bytes = struct.pack(">I", size)
            self._send_with_verification(size_bytes, f"tamaño ({size})")
            time.sleep(0.05)
            
            # 2. Envío principal con verificación estricta
            sent = 0
            view = memoryview(data)
            last_log = 0
            consecutive_fails = 0
            
            while sent < size:
                remaining = size - sent
                current_chunk_size = min(chunk_size, remaining)
                chunk = view[sent:sent + current_chunk_size]
                
                # Verificación pre-envío
                initial_out_buffer = self.ser.out_waiting
                
                try:
                    bytes_written = self.ser.write(chunk)
                    if bytes_written != len(chunk):
                        logging.warning(f"⚠️ Escritura parcial: {bytes_written}/{len(chunk)}")
                        consecutive_fails += 1
                        if consecutive_fails >= 5:
                            logging.error("❌ Demasiados fallos de escritura consecutivos")
                            return False
                    else:
                        consecutive_fails = 0
                    
                    # Flush inmediato y verificación
                    self.ser.flush()
                    sent += bytes_written
                    
                except serial.SerialTimeoutException:
                    logging.error(f"❌ Timeout escribiendo chunk en byte {sent}")
                    return False
                
                # CRÍTICO: Drenaje de buffer para últimos chunks
                if remaining <= 2048:  # Últimos 2KB
                    drain_timeout = time.time() + 10  # 10s para drenar
                    initial_buffer = self.ser.out_waiting
                    
                    while self.ser.out_waiting > 0 and time.time() < drain_timeout:
                        time.sleep(0.01)
                    
                    final_buffer = self.ser.out_waiting
                    if final_buffer > 0:
                        logging.warning(f"⚠️ Buffer no drenado: {initial_buffer} -> {final_buffer}")
                    
                    logging.info(f"🔍 Chunk final: {sent}/{size}, buffer: {initial_buffer}->{final_buffer}")
                
                # Pausa adaptativa (más larga al final)
                if remaining <= 1024:
                    time.sleep(base_sleep * 3)  # 3x más lento en último KB
                elif remaining <= 5120:
                    time.sleep(base_sleep * 2)  # 2x más lento en últimos 5KB
                else:
                    time.sleep(base_sleep)
                
                # Log de progreso
                pct = int(sent * 100 / size) if size else 100
                if pct - last_log >= 10 or remaining <= 5120:
                    logging.info(f"📦 Progreso: {sent}/{size} bytes ({pct}%)")
                    last_log = pct
            
            # 3. VERIFICACIÓN FINAL CRÍTICA
            logging.info("🔍 Verificación final...")
            
            # Esperar drenaje completo del buffer
            final_drain_start = time.time()
            max_drain_time = 15  # 15 segundos máximo
            
            while self.ser.out_waiting > 0:
                if time.time() - final_drain_start > max_drain_time:
                    logging.error(f"❌ TIMEOUT: Buffer no se vació ({self.ser.out_waiting} bytes pendientes)")
                    return False
                time.sleep(0.1)
                logging.debug(f"Drenando buffer: {self.ser.out_waiting} bytes")
            
            # Pausa adicional para estabilizar
            time.sleep(0.2)
            
            # Verificación de éxito
            if sent == size and self.ser.out_waiting == 0:
                logging.info("✅ Envío COMPLETAMENTE VERIFICADO")
                success = True
            else:
                logging.error(f"❌ Verificación falló: sent={sent}/{size}, buffer={self.ser.out_waiting}")
                success = False
            
            # 4. Marcadores finales (solo si envío exitoso)
            if success and send_end_markers:
                time.sleep(0.1)
                self._send_with_verification(END_MARKER, "marcador fin")
                time.sleep(0.02)
                self._send_with_verification(END_TEXT, "texto fin")
                logging.info("🏁 Marcadores finales enviados")
            
            return success
            
        except Exception as e:
            logging.error(f"❌ Error crítico durante envío: {e}")
            return False

    def _send_with_verification(self, data: bytes, description: str):
        """Envío con verificación de escritura completa"""
        try:
            bytes_written = self.ser.write(data)
            if bytes_written != len(data):
                raise Exception(f"Escritura incompleta de {description}: {bytes_written}/{len(data)}")
            self.ser.flush()
            logging.debug(f"✅ {description}: {len(data)} bytes")
        except Exception as e:
            logging.error(f"❌ Error enviando {description}: {e}")
            raise

    def send_file(self, path: str, **kwargs) -> bool:
        with open(path, "rb") as f:
            data = f.read()
        return self.send_bytes(data, **kwargs)
