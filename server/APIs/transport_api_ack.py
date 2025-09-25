#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transport_api_ack.py — API de transporte UART con verificación ACK
- Envío inicial + confirmación del cliente
- Retransmisión de bytes faltantes si es necesario
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

# Protocolo ACK
ACK_OK = "ACK_OK"
ACK_MISSING = "ACK_MISSING:"

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
                while self.ser.out_waiting > 0 and (time.time() - timeout_start) < 5:
                    time.sleep(0.1)
                self.ser.close()
                logging.info("🔌 UART cerrada")
        except:
            pass

    def _wait_for_ack(self, expected_size: int, timeout: float = 30) -> tuple[bool, int]:
        """Esperar ACK del cliente. Retorna (success, bytes_missing)"""
        logging.info("📋 Esperando ACK del cliente...")
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                    
                logging.info(f"📨 Cliente: {line}")
                
                if line == ACK_OK:
                    logging.info("✅ ACK_OK - Cliente recibió todo")
                    return True, 0
                elif line.startswith(ACK_MISSING):
                    try:
                        received = int(line.split(":")[1])
                        missing = expected_size - received
                        logging.warning(f"⚠️ ACK_MISSING - Faltan {missing} bytes")
                        return False, missing
                    except:
                        logging.error("❌ Formato ACK_MISSING inválido")
                        return False, 0
            except Exception as e:
                logging.debug(f"Error leyendo ACK: {e}")
                
            time.sleep(0.1)
        
        logging.warning("⏰ Timeout esperando ACK")
        return False, 0

    def _send_missing_bytes(self, data: bytes, start_offset: int, missing_count: int) -> bool:
        """Retransmitir bytes faltantes"""
        if start_offset >= len(data):
            logging.error(f"❌ Offset inválido: {start_offset} >= {len(data)}")
            return False
            
        end_offset = min(start_offset + missing_count, len(data))
        missing_data = data[start_offset:end_offset]
        
        logging.info(f"🔄 Retransmitiendo {len(missing_data)} bytes desde offset {start_offset}")
        
        try:
            # Marcador especial para retransmisión
            retry_marker = b"\xCC" * 4
            self.ser.write(retry_marker)
            self.ser.flush()
            time.sleep(0.02)
            
            # Enviar bytes faltantes directamente (sin preámbulo)
            chunk_size = 128  # Chunks más pequeños para retransmisión
            sent = 0
            
            while sent < len(missing_data):
                chunk_end = min(sent + chunk_size, len(missing_data))
                chunk = missing_data[sent:chunk_end]
                
                bytes_written = self.ser.write(chunk)
                self.ser.flush()
                sent += bytes_written
                
                # Pausa entre chunks para estabilidad
                time.sleep(0.01)
                
                if sent % 512 == 0 or sent == len(missing_data):
                    logging.info(f"🔄 Retransmisión: {sent}/{len(missing_data)} bytes")
            
            logging.info("✅ Retransmisión completada")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error en retransmisión: {e}")
            return False

    def send_bytes_with_ack(self, data: bytes, expected_size: int,
                           inter_chunk_sleep_ms: int = 0,
                           max_retries: int = 3) -> bool:
        """Envío con verificación ACK y retransmisión"""
        if not self.ser or not self.ser.is_open:
            logging.error("❌ UART no abierta")
            return False

        size = len(data)
        logging.info(f"📊 Enviando {size} bytes con verificación ACK...")

        try:
            # 1. Envío inicial (protocolo estándar)
            self.ser.write(START_MARKER)
            self.ser.flush()
            time.sleep(0.05)
            
            size_bytes = struct.pack(">I", size)
            self.ser.write(size_bytes)
            self.ser.flush()
            time.sleep(0.05)
            
            # Envío por chunks
            chunk_size = 512
            sent = 0
            base_sleep = max(0.003, inter_chunk_sleep_ms / 1000.0)
            
            while sent < size:
                chunk_end = min(sent + chunk_size, size)
                chunk = data[sent:chunk_end]
                
                self.ser.write(chunk)
                self.ser.flush()
                sent += chunk_end - sent
                
                if base_sleep > 0:
                    time.sleep(base_sleep)
                
                # Log cada 10%
                if sent % (size // 10) == 0 or sent == size:
                    pct = int(sent * 100 / size)
                    logging.info(f"📦 Progreso: {sent}/{size} bytes ({pct}%)")
            
            # Drenaje final
            self.ser.flush()
            time.sleep(0.2)
            
            # Marcadores finales
            self.ser.write(END_MARKER)
            self.ser.write(END_TEXT)
            self.ser.flush()
            
            logging.info("📤 Envío inicial completado, esperando ACK...")
            
            # 2. Ciclo de verificación y retransmisión
            for retry in range(max_retries + 1):
                if retry > 0:
                    logging.info(f"🔄 Intento de corrección #{retry}")
                
                # Esperar ACK
                ack_success, missing_bytes = self._wait_for_ack(expected_size, timeout=45)
                
                if ack_success:
                    logging.info("🎉 Transmisión verificada exitosamente")
                    return True
                    
                if missing_bytes <= 0:
                    logging.error("❌ No se pudo determinar bytes faltantes")
                    break
                
                if retry >= max_retries:
                    logging.error(f"❌ Máximo de reintentos alcanzado ({max_retries})")
                    break
                
                # Retransmitir bytes faltantes
                received_bytes = expected_size - missing_bytes
                success = self._send_missing_bytes(data, received_bytes, missing_bytes)
                
                if not success:
                    logging.error("❌ Falló retransmisión")
                    break
                    
                # Pausa antes del siguiente ACK
                time.sleep(0.5)
            
            logging.error("❌ Transmisión falló después de todos los reintentos")
            return False
            
        except Exception as e:
            logging.error(f"❌ Error crítico: {e}")
            return False

    def send_file_with_ack(self, path: str, expected_size: int, **kwargs) -> bool:
        with open(path, "rb") as f:
            data = f.read()
        return self.send_bytes_with_ack(data, expected_size, **kwargs)

    # Mantener métodos originales para compatibilidad
    def send_bytes(self, data: bytes, **kwargs) -> bool:
        return self.send_bytes_with_ack(data, len(data), **kwargs)

    def send_file(self, path: str, **kwargs) -> bool:
        with open(path, "rb") as f:
            data = f.read()
        return self.send_bytes_with_ack(data, len(data), **kwargs)
