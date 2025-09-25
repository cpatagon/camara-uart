#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente UART v5 con protocolo ACK - Confirmación de recepción
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
TIMEOUT_RESP = 15
START_MARKER = b'\xAA' * 10
RETRY_MARKER = b'\xCC' * 4  # Marcador de retransmisión
SIZE_BYTES = 4

# Delimitadores de comando
CMD_BEGIN = "<"
CMD_END = ">"

# Protocolo ACK
ACK_OK = "ACK_OK"
ACK_MISSING = "ACK_MISSING:"

class UARTClientACK:
    def __init__(self, port, baudrate=57600, timeout=8, rtscts=False, xonxoff=False):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.rtscts = rtscts
        self.xonxoff = xonxoff
        self.ser = None
        self.received_data = bytearray()

    def connect(self):
        """Conectar al puerto serial"""
        try:
            try:
                subprocess.run([
                    'stty', '-F', self.port,
                    'speed', str(self.baudrate),
                    'cs8', '-cstopb', '-parenb', 'raw', '-crtscts',
                    '-echo', '-echoe', '-echok'
                ], check=True, timeout=3)
                time.sleep(0.2)
            except Exception as e:
                logging.debug(f"stty setup: {e}")

            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout,
                write_timeout=2,
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )

            for _ in range(3):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)

            logging.info(f"✅ Conectado: {self.port} @ {self.baudrate}")
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
            time.sleep(1.0)
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

    def send_ack(self, received_bytes: int, expected_bytes: int):
        """Enviar confirmación ACK al servidor"""
        try:
            if received_bytes == expected_bytes:
                ack_msg = f"{ACK_OK}\r\n"
                logging.info("📨 Enviando ACK_OK")
            else:
                ack_msg = f"{ACK_MISSING}{received_bytes}\r\n"
                missing = expected_bytes - received_bytes
                logging.info(f"📨 Enviando ACK_MISSING: faltan {missing} bytes")
            
            self.ser.write(ack_msg.encode('utf-8'))
            self.ser.flush()
            return True
        except Exception as e:
            logging.error(f"❌ Error enviando ACK: {e}")
            return False

    def _wait_start_marker(self, max_wait=30):
        """Esperar marcador de inicio"""
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

    def _wait_retry_marker(self, max_wait=10):
        """Esperar marcador de retransmisión"""
        logging.info("🔄 Buscando marcador de retransmisión...")
        deadline = time.time() + max_wait
        window = bytearray()

        while time.time() < deadline:
            b = self.ser.read(1)
            if not b:
                continue
            window += b
            if len(window) > len(RETRY_MARKER):
                window = window[-len(RETRY_MARKER):]
            if window == RETRY_MARKER:
                logging.info("✅ Marcador de retransmisión encontrado")
                return True
        return False

    def _read_size_header(self):
        """Leer cabecera de tamaño"""
        size_data = b''
        deadline = time.time() + 10

        while len(size_data) < SIZE_BYTES and time.time() < deadline:
            chunk = self.ser.read(SIZE_BYTES - len(size_data))
            if chunk:
                size_data += chunk

        if len(size_data) != SIZE_BYTES:
            logging.error("❌ No se pudieron leer 4 bytes de tamaño")
            return None

        transmitted_size = struct.unpack('>I', size_data)[0]
        logging.info(f"📊 Tamaño transmitido: {transmitted_size} bytes")
        return transmitted_size

    def _read_exact(self, nbytes, log_progress=True):
        """Leer exactamente nbytes"""
        start_pos = len(self.received_data)
        chunk_size = 4096
        last_progress = 0
        
        while len(self.received_data) - start_pos < nbytes:
            remaining = nbytes - (len(self.received_data) - start_pos)
            to_read = min(chunk_size, remaining)
            
            chunk = self.ser.read(to_read)
            if chunk:
                self.received_data.extend(chunk)
                
                if log_progress and nbytes >= 10000:
                    progress = int((len(self.received_data) - start_pos) * 100 / nbytes)
                    if progress - last_progress >= 10:
                        received = len(self.received_data) - start_pos
                        logging.info(f"📊 Progreso: {received}/{nbytes} bytes ({progress}%)")
                        last_progress = progress
            else:
                # Timeout en lectura
                break
        
        received = len(self.received_data) - start_pos
        return received == nbytes

    def receive_with_ack(self, file_size, save_path=None, max_correction_cycles=3):
        """Recepción con protocolo ACK y corrección"""
        try:
            logging.info("📥 Iniciando recepción con ACK...")

            # 1. Recepción inicial
            if not self._wait_start_marker():
                return False

            transmitted_size = self._read_size_header()
            if not transmitted_size:
                return False

            logging.info(f"📊 Esperado: {file_size}, Transmitido: {transmitted_size}")

            # Leer datos principales
            self.received_data = bytearray()
            success = self._read_exact(transmitted_size)

            # Drenar marcadores finales
            try:
                self.ser.timeout = 0.5
                extra = self.ser.read(1000)
                if extra:
                    logging.debug(f"🔚 Marcadores finales drenados: {len(extra)} bytes")
            except:
                pass
            finally:
                self.ser.timeout = self.timeout

            received_initial = len(self.received_data)
            logging.info(f"📊 Recepción inicial: {received_initial}/{transmitted_size} bytes")

            # 2. Enviar ACK inicial
            self.send_ack(received_initial, transmitted_size)

            # 3. Ciclo de corrección si es necesario
            for cycle in range(max_correction_cycles):
                if len(self.received_data) >= transmitted_size:
                    logging.info("✅ Recepción completa verificada")
                    break
                
                logging.info(f"🔄 Ciclo de corrección #{cycle + 1}")
                
                # Esperar retransmisión
                if not self._wait_retry_marker(max_wait=15):
                    logging.warning("⏰ No llegó retransmisión")
                    break
                
                # Leer bytes de corrección
                missing_bytes = transmitted_size - len(self.received_data)
                logging.info(f"🔄 Leyendo {missing_bytes} bytes de corrección...")
                
                correction_success = self._read_exact(missing_bytes, log_progress=False)
                received_total = len(self.received_data)
                
                logging.info(f"📊 Después de corrección: {received_total}/{transmitted_size} bytes")
                
                # Enviar ACK de corrección
                self.send_ack(received_total, transmitted_size)
                
                if received_total >= transmitted_size:
                    logging.info("✅ Corrección exitosa")
                    break

            # 4. Resultado final
            bytes_received = len(self.received_data)
            success = bytes_received >= transmitted_size

            # Truncar si recibimos más bytes de los esperados
            if bytes_received > transmitted_size:
                self.received_data = self.received_data[:transmitted_size]
                logging.info(f"✂️ Truncado a {transmitted_size} bytes")

            # Verificación JPEG
            if len(self.received_data) >= 4:
                if self.received_data[:2] == b'\xff\xd8':
                    logging.info("✅ Cabecera JPEG correcta")
                else:
                    logging.warning("⚠️ Cabecera JPEG incorrecta")
                
                if self.received_data[-2:] == b'\xff\xd9':
                    logging.info("✅ Final JPEG correcto")
                else:
                    logging.warning("⚠️ Final JPEG incorrecto")

            # 5. Guardar archivo
            if not save_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"imagen_ack_{timestamp}.jpg"

            if self.received_data:
                with open(save_path, 'wb') as f:
                    f.write(self.received_data)
                logging.info(f"💾 Imagen guardada: {save_path}")

            return success

        except Exception as e:
            logging.error(f"❌ Error recepción ACK: {e}")
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
    parser = argparse.ArgumentParser(description='Cliente UART v5 con ACK')
    parser.add_argument('port', help='Puerto serial')
    parser.add_argument('--resp-timeout', type=int, default=45)
    parser.add_argument('--resolution', '-r', default='HD_READY')
    parser.add_argument('--output', '-o', help='Ruta de salida')
    parser.add_argument('--baudrate', '-b', type=int, default=57600)
    parser.add_argument('--rtscts', action='store_true')
    parser.add_argument('--xonxoff', action='store_true')

    args = parser.parse_args()

    resp_timeout = int(os.environ.get('RESP_TIMEOUT', args.resp_timeout))

    print("=" * 60)
    print("Cliente UART v5 con Protocolo ACK")
    print("=" * 60)

    client = UARTClientACK(
        port=args.port,
        baudrate=args.baudrate,
        timeout=8,
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
        success = client.receive_with_ack(file_size_ascii, args.output)

        if success:
            logging.info("=" * 60)
            logging.info("✅ PROCESO COMPLETO EXITOSO CON ACK")
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
