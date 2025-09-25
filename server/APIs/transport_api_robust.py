#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transport_api_robust.py — API de transporte UART robusta
- Combina lo mejor del protocolo ACK + mejoras de sincronización
- Elimina la desaceleración artificial problemática
- Implementa verificación bidireccional real
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

# Protocolo ACK mejorado
ACK_READY = "ACK_READY"
ACK_OK = "ACK_OK"
ACK_MISSING = "ACK_MISSING:"
ACK_ERROR = "ACK_ERROR"

class UartTransportRobust:
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
            
            # Limpieza inicial mejorada
            for _ in range(5):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)
            
            logging.info(f"✅ UART Robusta: {self.port} @ {self.baudrate} (rtscts={self.rtscts}, xonxoff={self.xonxoff})")
            return True
        except Exception as e:
            logging.error(f"❌ UART open: {e}")
            return False

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                # Cierre más suave
                self.ser.flush()
                timeout_start = time.time()
                while self.ser.out_waiting > 0 and (time.time() - timeout_start) < 10:
                    time.sleep(0.1)
                
                self.ser.reset_output_buffer()
                self.ser.reset_input_buffer()
                self.ser.close()
                logging.info("🔌 UART robusta cerrada")
        except Exception as e:
            logging.debug(f"Error cerrando UART: {e}")

    def _wait_for_client_ready(self, timeout: float = 30) -> bool:
        """Esperar que el cliente confirme estar listo para recibir"""
        logging.info("📋 Esperando que cliente esté listo...")
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line == ACK_READY:
                    logging.info("✅ Cliente listo para recibir")
                    return True
                elif line:
                    logging.debug(f"📨 Cliente (esperando ready): {line}")
            except Exception as e:
                logging.debug(f"Error leyendo ready: {e}")
                
            time.sleep(0.1)
        
        logging.warning("⏰ Timeout esperando cliente listo")
        return False

    def _wait_for_ack(self, expected_size: int, timeout: float = 45) -> tuple[bool, int]:
        """Esperar ACK del cliente con timeout extendido"""
        logging.info("📋 Esperando confirmación final del cliente...")
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                    
                logging.info(f"📨 Cliente: {line}")
                
                if line == ACK_OK:
                    logging.info("✅ ACK_OK - Cliente confirmó recepción completa")
                    return True, 0
                elif line.startswith(ACK_MISSING):
                    try:
                        received = int(line.split(":")[1])
                        missing = expected_size - received
                        logging.warning(f"⚠️ Faltan {missing} bytes (cliente recibió {received})")
                        return False, missing
                    except:
                        logging.error("❌ Formato ACK_MISSING inválido")
                        return False, expected_size
                elif line == ACK_ERROR:
                    logging.error("❌ Cliente reportó error")
                    return False, expected_size
                    
            except Exception as e:
                logging.debug(f"Error leyendo ACK: {e}")
                
            time.sleep(0.1)
        
        logging.warning("⏰ Timeout esperando ACK final")
        return False, 0

    def _send_missing_bytes(self, data: bytes, start_offset: int, missing_count: int) -> bool:
        """Retransmitir bytes faltantes de manera robusta"""
        if start_offset >= len(data) or missing_count <= 0:
            logging.error(f"❌ Parámetros retransmisión inválidos: offset={start_offset}, missing={missing_count}")
            return False
            
        end_offset = min(start_offset + missing_count, len(data))
        missing_data = data[start_offset:end_offset]
        
        logging.info(f"🔄 Retransmitiendo {len(missing_data)} bytes desde offset {start_offset}")
        
        try:
            # Marcador especial para retransmisión
            retry_marker = b"\xCC" * 4
            self.ser.write(retry_marker)
            self.ser.flush()
            time.sleep(0.1)  # Pausa para que cliente detecte retransmisión
            
            # Envío con chunks más pequeños y pausas
            chunk_size = 64  # Chunks muy pequeños para máxima confiabilidad
            sent = 0
            
            while sent < len(missing_data):
                chunk_end = min(sent + chunk_size, len(missing_data))
                chunk = missing_data[sent:chunk_end]
                
                bytes_written = self.ser.write(chunk)
                self.ser.flush()
                sent += bytes_written
                
                # Pausa más larga para estabilidad
                time.sleep(0.02)
                
                if sent % 256 == 0 or sent == len(missing_data):
                    logging.info(f"🔄 Retransmisión: {sent}/{len(missing_data)} bytes")
            
            # Pausa final después de retransmisión
            time.sleep(0.5)
            logging.info("✅ Retransmisión completada")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error en retransmisión: {e}")
            return False

    def _calculate_smart_sleep(self, sent_bytes: int, total_bytes: int, base_sleep_ms: int) -> float:
        """Calcular pausa inteligente - SIN desaceleración artificial problemática"""
        base_sleep = max(0.001, base_sleep_ms / 1000.0)
        
        # Velocidad constante - eliminamos la desaceleración que causaba los chunks de 110ms
        return base_sleep
        
        # NOTA: Comentamos la lógica de desaceleración que causaba el problema:
        # if remaining_bytes <= 256: return base_sleep * 25  # ESTO causaba 125ms
        # if remaining_bytes <= 512: return base_sleep * 20  # ESTO causaba 100ms

    def send_bytes_robust(self, data: bytes,
                         chunk_size: int = DEFAULT_CHUNK,
                         inter_chunk_sleep_ms: int = 0,
                         max_retries: int = 2,
                         wait_client_ready: bool = True) -> bool:
        """Envío robusto con protocolo ACK mejorado"""
        if not self.ser or not self.ser.is_open:
            logging.error("❌ UART no abierta")
            return False

        size = len(data)
        logging.info(f"📊 Envío ROBUSTO: {size} bytes con protocolo ACK mejorado")

        try:
            # 0. Opcional: Esperar que cliente esté listo
            if wait_client_ready:
                if not self._wait_for_client_ready(timeout=30):
                    logging.warning("⚠️ Cliente no confirmó estar listo, continuando...")

            # 1. Preámbulo del protocolo
            logging.info("📤 Enviando preámbulo...")
            self.ser.write(START_MARKER)
            self.ser.flush()
            time.sleep(0.1)  # Pausa fija, no variable
            
            size_bytes = struct.pack(">I", size)
            self.ser.write(size_bytes)
            self.ser.flush()
            time.sleep(0.1)  # Pausa fija, no variable
            
            # 2. Envío principal con velocidad CONSTANTE (sin desaceleración)
            logging.info("📦 Iniciando envío principal...")
            sent = 0
            view = memoryview(data)
            last_log = 0
            base_sleep = self._calculate_smart_sleep(0, size, inter_chunk_sleep_ms)
            
            while sent < size:
                remaining = size - sent
                current_chunk_size = min(chunk_size, remaining)
                chunk = view[sent:sent + current_chunk_size]
                
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
                
                # Pausa CONSTANTE (eliminamos la lógica de desaceleración)
                if base_sleep > 0:
                    time.sleep(base_sleep)
                
                # Log de progreso
                pct = int(sent * 100 / size) if size else 100
                if pct - last_log >= 10:
                    logging.info(f"📦 Progreso constante: {sent}/{size} bytes ({pct}%)")
                    last_log = pct
            
            # 3. Sincronización final robusta
            logging.info("🔍 Sincronización final robusta...")
            self.ser.flush()
            
            # Drenaje con timeout extendido
            drain_start = time.time()
            max_drain_time = 15
            
            while self.ser.out_waiting > 0:
                if time.time() - drain_start > max_drain_time:
                    logging.error(f"❌ TIMEOUT drenaje: {self.ser.out_waiting} bytes pendientes")
                    return False
                time.sleep(0.1)
                
                elapsed = time.time() - drain_start
                if int(elapsed) % 3 == 0 and elapsed > 1:
                    logging.info(f"⏳ Drenando: {self.ser.out_waiting} bytes ({elapsed:.1f}s)")
            
            # 4. Pausa de estabilización antes de marcadores
            logging.info("⏳ Pausa de estabilización...")
            time.sleep(1.0)  # Tiempo fijo para que cliente procese
            
            # 5. Marcadores finales
            self.ser.write(END_MARKER)
            self.ser.flush()
            time.sleep(0.2)
            self.ser.write(END_TEXT)
            self.ser.flush()
            time.sleep(0.2)
            
            logging.info("📤 Envío completado, iniciando verificación ACK...")
            
            # 6. Ciclo de verificación y corrección
            for retry in range(max_retries + 1):
                if retry > 0:
                    logging.info(f"🔄 Intento de corrección #{retry}/{max_retries}")
                
                # Esperar ACK con timeout extendido
                ack_success, missing_bytes = self._wait_for_ack(size, timeout=60)
                
                if ack_success:
                    logging.info("🎉 ¡TRANSMISIÓN ROBUSTA COMPLETADA CON ÉXITO!")
                    return True
                
                if missing_bytes <= 0:
                    logging.error("❌ No se pudo determinar corrección necesaria")
                    break
                
                if retry >= max_retries:
                    logging.error(f"❌ Máximo de reintentos alcanzado ({max_retries})")
                    break
                
                # Calcular offset y retransmitir
                received_bytes = size - missing_bytes
                success = self._send_missing_bytes(data, received_bytes, missing_bytes)
                
                if not success:
                    logging.error("❌ Falló retransmisión")
                    break
                    
                # Pausa antes del siguiente ciclo ACK
                time.sleep(1.0)
            
            logging.error("❌ Transmisión falló después de todos los reintentos")
            return False
            
        except Exception as e:
            logging.error(f"❌ Error crítico en envío robusto: {e}")
            return False

    # Métodos de compatibilidad
    def send_bytes(self, data: bytes, **kwargs) -> bool:
        """Método de compatibilidad - redirige al robusto"""
        return self.send_bytes_robust(data, **kwargs)

    def send_file(self, path: str, **kwargs) -> bool:
        """Envío de archivo robusto"""
        with open(path, "rb") as f:
            data = f.read()
        return self.send_bytes_robust(data, **kwargs)
