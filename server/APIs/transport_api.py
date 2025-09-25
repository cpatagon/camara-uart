#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transport_api.py — API de transporte UART con desaceleración gradual
- Transmisión normal hasta últimos KB
- Desaceleración progresiva para sincronización perfecta
- Verificación final robusta
"""

import time
import struct
import logging
import serial

START_MARKER = b"\xAA" * 10
END_MARKER   = b"\xBB" * 10
END_TEXT     = b"<FIN_TRANSMISION>\r\n"
SIZE_BYTES   = 4
DEFAULT_CHUNK = 512

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
                write_timeout=15,
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )
            
            # Limpieza inicial
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

    def _calculate_adaptive_sleep(self, remaining_bytes: int, base_sleep_ms: int) -> float:
        """Calcular pausa adaptativa basada en bytes restantes"""
        base_sleep = max(0.003, base_sleep_ms / 1000.0)
        
        if remaining_bytes <= 512:
            # Últimos 512 bytes: MUY lento
            return base_sleep * 10  # 10x más lento
        elif remaining_bytes <= 1024:
            # Últimos 1KB: Muy lento
            return base_sleep * 6   # 6x más lento
        elif remaining_bytes <= 2048:
            # Últimos 2KB: Lento
            return base_sleep * 4   # 4x más lento
        elif remaining_bytes <= 5120:
            # Últimos 5KB: Más lento
            return base_sleep * 2   # 2x más lento
        else:
            # Transmisión normal
            return base_sleep

    def send_bytes(self, data: bytes,
                   chunk_size: int = DEFAULT_CHUNK,
                   inter_chunk_sleep_ms: int = 0,
                   send_end_markers: bool = True) -> bool:
        """
        Envío con desaceleración gradual en los últimos bytes
        """
        if not self.ser or not self.ser.is_open:
            logging.error("❌ UART no abierta")
            return False

        size = len(data)
        
        # Ajuste de parámetros base según tamaño total
        if size > 200000:
            chunk_size = min(chunk_size, 256)
            base_sleep_ms = max(inter_chunk_sleep_ms, 8)
        elif size > 100000:
            chunk_size = min(chunk_size, 512)
            base_sleep_ms = max(inter_chunk_sleep_ms, 5)
        else:
            base_sleep_ms = max(inter_chunk_sleep_ms, 3)
        
        logging.info(f"📊 Enviando {size} bytes con desaceleración gradual...")
        logging.info(f"📊 Chunks: {chunk_size}, sleep base: {base_sleep_ms}ms")

        try:
            # 1. Preámbulo
            self._send_with_verification(START_MARKER, "marcador inicio")
            time.sleep(0.05)
            
            size_bytes = struct.pack(">I", size)
            self._send_with_verification(size_bytes, f"tamaño ({size})")
            time.sleep(0.05)
            
            # 2. Envío principal con desaceleración gradual
            sent = 0
            view = memoryview(data)
            last_log = 0
            
            while sent < size:
                remaining = size - sent
                current_chunk_size = min(chunk_size, remaining)
                chunk = view[sent:sent + current_chunk_size]
                
                # Calcular pausa adaptativa
                adaptive_sleep = self._calculate_adaptive_sleep(remaining, base_sleep_ms)
                
                # Log detallado en zona de desaceleración
                if remaining <= 5120:
                    logging.info(f"🐌 Desaceleración: {sent}/{size} - "
                               f"faltan: {remaining} - sleep: {adaptive_sleep*1000:.1f}ms")
                
                # Envío del chunk
                try:
                    bytes_written = self.ser.write(chunk)
                    if bytes_written != len(chunk):
                        logging.warning(f"⚠️ Escritura parcial: {bytes_written}/{len(chunk)}")
                    
                    self.ser.flush()
                    sent += bytes_written
                    
                except serial.SerialTimeoutException:
                    logging.error(f"❌ Timeout escribiendo en byte {sent}")
                    return False
                
                # Pausa adaptativa
                if adaptive_sleep > 0:
                    time.sleep(adaptive_sleep)
                
                # Drenaje extra para últimos chunks
                if remaining <= 2048:
                    drain_start = time.time()
                    initial_buffer = self.ser.out_waiting
                    
                    while self.ser.out_waiting > 0 and (time.time() - drain_start) < 5:
                        time.sleep(0.01)
                    
                    final_buffer = self.ser.out_waiting
                    if remaining <= 512:  # Solo log para últimos 512 bytes
                        logging.info(f"🔍 Buffer drain: {initial_buffer}->{final_buffer}")
                
                # Log de progreso
                pct = int(sent * 100 / size) if size else 100
                if pct - last_log >= 10 or remaining <= 5120:
                    logging.info(f"📦 Progreso: {sent}/{size} bytes ({pct}%)")
                    last_log = pct
            
            # 3. Verificación final extendida
            logging.info("🔍 Verificación final extendida...")
            
            # Drenaje final con timeout largo
            final_drain_start = time.time()
            max_drain_time = 20  # 20 segundos para estar seguros
            
            while self.ser.out_waiting > 0:
                if time.time() - final_drain_start > max_drain_time:
                    logging.error(f"❌ TIMEOUT final: Buffer no se vació ({self.ser.out_waiting} bytes)")
                    return False
                time.sleep(0.1)
                
                # Log cada 2 segundos
                elapsed = time.time() - final_drain_start
                if int(elapsed) % 2 == 0 and elapsed > 1:
                    logging.info(f"⏳ Drenando buffer final: {self.ser.out_waiting} bytes ({elapsed:.1f}s)")
            
            # Pausa extra de estabilización
            time.sleep(0.5)
            
            # Verificación de éxito
            if sent == size and self.ser.out_waiting == 0:
                logging.info("✅ Envío COMPLETAMENTE VERIFICADO con desaceleración")
                success = True
            else:
                logging.error(f"❌ Verificación falló: sent={sent}/{size}, buffer={self.ser.out_waiting}")
                success = False
            
            # 4. Marcadores finales con pausa extra
            if success and send_end_markers:
                time.sleep(0.2)  # Pausa extra antes de marcadores
                self._send_with_verification(END_MARKER, "marcador fin")
                time.sleep(0.1)
                self._send_with_verification(END_TEXT, "texto fin")
                time.sleep(0.1)  # Pausa extra después de marcadores
                logging.info("🏁 Marcadores finales enviados con pausas extendidas")
            
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
