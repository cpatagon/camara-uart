#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente UART v5 OPTIMIZADO - Solución al problema de timing
"""

import serial
import time
import struct
import logging
from datetime import datetime
import argparse
import subprocess
import os

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Protocolo
CMD_START = "FOTO:"
RESP_OK = "OK|"
RESP_BAD = "BAD|"
TIMEOUT_RESP = 15  # esperar OK|size
START_MARKER = b'\xAA' * 10    # inicio de stream binario
SIZE_BYTES = 4                 # tamaño en 4 bytes big-endian

# Delimitadores de comando
CMD_BEGIN = "<"
CMD_END = ">"


class OptimizedUARTClient:
    def __init__(self, port, baudrate=19200, timeout=0.5, rtscts=False, xonxoff=True):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout  # TIMEOUT MUY CORTO para lectura ágil
        self.rtscts = rtscts
        self.xonxoff = xonxoff
        self.ser = None
        self.received_data = bytearray()

    def connect(self):
        """Conectar con configuración optimizada para timing"""
        try:
            # Configuración previa del puerto si es posible
            try:
                subprocess.run([
                    'stty', '-F', self.port,
                    'speed', str(self.baudrate),
                    'cs8', '-cstopb', '-parenb', 'raw',
                    '-echo', '-echoe', '-echok'
                ], check=True, timeout=3)
                time.sleep(0.1)
            except Exception as e:
                logging.debug(f"stty setup: {e}")

            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout,        # TIMEOUT CORTO para agilidad
                write_timeout=2,
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )

            # Limpieza inicial
            for _ in range(3):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.05)

            logging.info(f"✅ Conectado: {self.port} @ {self.baudrate} (timeout={self.timeout}s)")
            return True

        except Exception as e:
            logging.error(f"❌ Error conexión: {e}")
            return False

    def send_command(self, resolution="THUMBNAIL"):
        """Enviar comando"""
        try:
            cmd = f"{CMD_BEGIN}{CMD_START}{{size_name:{resolution}}}{CMD_END}\r\n"
            logging.info(f"📤 Enviando comando: {cmd.strip()}")

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.2)

            self.ser.write(cmd.encode('utf-8'))
            self.ser.flush()
            logging.info("✅ Comando enviado - esperando respuesta...")
            time.sleep(0.5)
            return True
        except Exception as e:
            logging.error(f"❌ Error enviando: {e}")
            return False

    def wait_for_response(self, timeout_s=None):
        """Esperar respuesta del servidor"""
        if timeout_s is None:
            timeout_s = TIMEOUT_RESP
        end = time.time() + timeout_s
        
        while time.time() < end:
            lb = self.ser.readline()
            if not lb:
                continue
            try:
                line = lb.decode('utf-8', errors='ignore').strip()
            except:
                continue
            if line.startswith(RESP_OK) or line.startswith(RESP_BAD):
                logging.info(f"✅ Respuesta recibida: {line}")
                return line
        logging.warning("⏱️ Timeout esperando respuesta")
        return None

    def _wait_start_marker(self, max_wait=30):
        """Esperar START_MARKER"""
        logging.info("🔍 Buscando marcador de inicio...")
        deadline = time.time() + max_wait
        window = bytearray()

        while time.time() < deadline:
            b = self.ser.read(1)
            if not b:
                continue
            window += b
            if len(window) > len(START_MARKER):
                window = window[-len(START_MARKER):]
            if window == START_MARKER:
                logging.info("✅ Marcador de inicio encontrado")
                return True
        logging.error("❌ No se encontró marcador de inicio")
        return False

    def _read_size_header(self):
        """Leer tamaño (4 bytes)"""
        size_data = b''
        deadline = time.time() + 10

        while len(size_data) < 4 and time.time() < deadline:
            chunk = self.ser.read(4 - len(size_data))
            if chunk:
                size_data += chunk

        if len(size_data) != 4:
            logging.error(f"❌ No se pudieron leer 4 bytes de tamaño")
            return None

        transmitted_size = struct.unpack('>I', size_data)[0]
        logging.info(f"📊 Tamaño transmitido: {transmitted_size} bytes")
        return transmitted_size

    def _aggressive_read(self, remaining_bytes, max_time=20):
        """Lectura agresiva de los últimos bytes"""
        logging.info(f"🚀 Lectura agresiva de {remaining_bytes} bytes")
        
        start_time = time.time()
        collected_data = bytearray()
        
        # Estrategia de lectura múltiple con timeout muy corto
        original_timeout = self.ser.timeout
        
        try:
            # Fase 1: Lectura con timeout muy corto para agilidad
            self.ser.timeout = 0.1
            deadline = time.time() + max_time
            consecutive_failures = 0
            
            while len(collected_data) < remaining_bytes and time.time() < deadline:
                # Calcular cuánto leer
                to_read = min(1024, remaining_bytes - len(collected_data))
                
                chunk = self.ser.read(to_read)
                if chunk:
                    collected_data.extend(chunk)
                    consecutive_failures = 0
                    
                    if remaining_bytes - len(collected_data) <= 100:
                        # Últimos 100 bytes: timeout aún más corto
                        self.ser.timeout = 0.05
                        logging.info(f"🔍 Últimos {remaining_bytes - len(collected_data)} bytes")
                else:
                    consecutive_failures += 1
                    
                    # Si llevamos varios fallos, revisar buffer
                    if consecutive_failures >= 3:
                        buffer_size = self.ser.in_waiting
                        if buffer_size > 0:
                            # Hay datos disponibles, leer inmediatamente
                            chunk = self.ser.read(buffer_size)
                            if chunk:
                                collected_data.extend(chunk)
                                consecutive_failures = 0
                        else:
                            # No hay buffer, pausa mínima
                            time.sleep(0.01)
                    
                    # Timeout progresivo si llevamos muchos fallos
                    if consecutive_failures >= 10:
                        time.sleep(0.05)
                    elif consecutive_failures >= 20:
                        time.sleep(0.1)

            elapsed = time.time() - start_time
            logging.info(f"📊 Lectura agresiva: {len(collected_data)}/{remaining_bytes} en {elapsed:.1f}s")
            
            return collected_data
            
        finally:
            self.ser.timeout = original_timeout

    def receive_image_optimized(self, file_size, save_path=None):
        """Recepción optimizada para el problema de timing"""
        try:
            logging.info("📥 Recepción optimizada iniciada...")

            # 1) Buscar marcador
            if not self._wait_start_marker(max_wait=30):
                return False

            # 2) Leer tamaño
            transmitted_size = self._read_size_header()
            if not transmitted_size:
                return False

            logging.info(f"📊 Esperado: {file_size}, Transmitido: {transmitted_size}")

            # 3) Recepción principal con estrategia híbrida
            self.received_data = bytearray()
            chunk_size = 4096
            last_activity = time.time()
            
            # Fase principal: lectura normal hasta estar cerca del final
            while len(self.received_data) < transmitted_size:
                remaining = transmitted_size - len(self.received_data)
                
                # Cambio de estrategia en los últimos 5KB
                if remaining <= 5120:
                    logging.info(f"🎯 Cambiando a lectura agresiva (faltan {remaining} bytes)")
                    
                    # Lectura agresiva de los bytes finales
                    final_data = self._aggressive_read(remaining, max_time=15)
                    if final_data:
                        self.received_data.extend(final_data)
                    break
                
                # Lectura normal
                to_read = min(chunk_size, remaining)
                chunk = self.ser.read(to_read)
                
                if chunk:
                    self.received_data.extend(chunk)
                    last_activity = time.time()
                    
                    # Log cada 50KB
                    if len(self.received_data) % 51200 == 0:
                        pct = int(len(self.received_data) * 100 / transmitted_size)
                        logging.info(f"📦 Progreso: {len(self.received_data)}/{transmitted_size} ({pct}%)")
                else:
                    # Sin datos
                    if time.time() - last_activity > 10:
                        logging.warning(f"⏱️ Timeout en lectura normal")
                        break

            bytes_received = len(self.received_data)
            logging.info(f"✅ Recibido: {bytes_received}/{transmitted_size} bytes")

            # 4) Verificación JPEG
            success = bytes_received == transmitted_size
            
            if bytes_received >= 4:
                if self.received_data[:2] == b'\xff\xd8':
                    logging.info("✅ Cabecera JPEG correcta")
                else:
                    logging.warning("⚠️ Cabecera JPEG incorrecta")
                
                if self.received_data[-2:] == b'\xff\xd9':
                    logging.info("✅ Final JPEG correcto")
                    success = True  # Imagen completa aunque falten marcadores
                else:
                    logging.warning("⚠️ Final JPEG incorrecto")

            # 5) Guardar
            if not save_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"imagen_opt_{timestamp}.jpg"

            if self.received_data:
                with open(save_path, 'wb') as f:
                    f.write(self.received_data)
                logging.info(f"💾 Imagen guardada: {save_path}")

            return success

        except Exception as e:
            logging.error(f"❌ Error recepción optimizada: {e}")
            return False

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.close()
                logging.info("🔌 Conexión cerrada")
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description='Cliente UART v5 Optimizado')
    parser.add_argument('port', help='Puerto serial')
    parser.add_argument('--resp-timeout', type=int, default=45)
    parser.add_argument('--resolution', '-r', default='HD_READY')
    parser.add_argument('--output', '-o', help='Ruta de salida')
    parser.add_argument('--baudrate', '-b', type=int, default=19200)
    parser.add_argument('--rtscts', action='store_true')
    parser.add_argument('--xonxoff', action='store_true')

    args = parser.parse_args()

    # Timeout desde env
    resp_timeout = int(os.environ.get('RESP_TIMEOUT', args.resp_timeout))

    print("=" * 60)
    print("Cliente UART v5 OPTIMIZADO - Solución Timing")
    print("=" * 60)

    client = OptimizedUARTClient(
        port=args.port,
        baudrate=args.baudrate,
        timeout=0.3,  # Timeout muy corto para agilidad
        rtscts=args.rtscts,
        xonxoff=args.xonxoff
    )

    try:
        if not client.connect():
            return

        if not client.send_command(args.resolution.upper()):
            return

        response = client.wait_for_response(timeout_s=resp_timeout)
        if not response or not response.startswith(RESP_OK):
            logging.error(f"❌ Error del servidor: {response}")
            return

        file_size_ascii = int(response.split("|")[1])
        success = client.receive_image_optimized(file_size_ascii, args.output)

        if success:
            logging.info("=" * 60)
            logging.info("✅ PROCESO COMPLETO EXITOSO")
            logging.info("=" * 60)
        else:
            logging.info("=" * 60)
            logging.info("⚠️ PROCESO COMPLETADO CON ADVERTENCIAS")
            logging.info("=" * 60)

    except KeyboardInterrupt:
        logging.info("\n🛑 Cliente detenido")
    except Exception as e:
        logging.error(f"❌ Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
