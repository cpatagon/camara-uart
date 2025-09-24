#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente UART v4.1 - Recepción por tamaño exacto (robusto)
"""

import serial
import time
import struct
import logging
from datetime import datetime
import argparse
import subprocess

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


class UARTPhotoClient:
    def __init__(self, port, baudrate=57600, timeout=8, rtscts=False, xonxoff=False):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.rtscts = rtscts
        self.xonxoff = xonxoff
        self.ser = None
        self.received_data = bytearray()

    def connect(self):
        """Conectar al puerto serial con configuración robusta."""
        try:
            # Intento de preparar puerto (no crítico si falla)
            try:
                subprocess.run([
                    'stty', '-F', self.port,
                    'speed', str(self.baudrate),
                    'cs8', '-cstopb', '-parenb', 'raw', '-crtscts',
                    '-echo', '-echoe', '-echok'
                ], check=True, timeout=3)
                time.sleep(0.2)
            except Exception as e:
                logging.debug(f"(stty opcional) {e}")

            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout,        # lectura bloqueante con timeout
                write_timeout=2,
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )

            # Limpieza inicial
            for _ in range(3):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)

            logging.info(f"✅ Conectado: {self.port} @ {self.baudrate} (rtscts={self.rtscts}, xonxoff={self.xonxoff})")
            return True

        except Exception as e:
            logging.error(f"❌ Error conexión: {e}")
            return False

    def send_command(self, resolution="THUMBNAIL"):
        """Enviar comando UNA SOLA VEZ."""
        try:
            cmd = f"{CMD_BEGIN}{CMD_START}{{size_name:{resolution}}}{CMD_END}\r\n"
            logging.info(f"📤 Enviando comando: {cmd.strip()}")

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.2)

            self.ser.write(cmd.encode('utf-8'))
            self.ser.flush()
            logging.info("✅ Comando enviado - esperando respuesta...")
            time.sleep(1.0)  # pequeño respiro para el servidor
            return True
        except Exception as e:
            logging.error(f"❌ Error enviando: {e}")
            return False

    def wait_for_response(self):
        if timeout_s is None:
            timeout_s = TIMEOUT_RESP
    end = time.time() + timeout_s
        line_bytes = bytearray()
        while time.time() < end:
            lb = self.ser.readline()  # lee solo hasta \n
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
        """Esperar START_MARKER con ventana deslizante."""
        logging.info("🔍 Buscando marcador de inicio...")
        deadline = time.time() + max_wait
        window = bytearray()

        while time.time() < deadline:
            b = self.ser.read(1)  # respeta self.timeout
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

    def _read_exact(self, nbytes, inactivity_timeout=30, chunk_size=4096, log_label=""):
        """Leer exactamente nbytes, con timeout por inactividad."""
        remaining = nbytes
        last_data_time = time.time()
        got = 0
        last_progress = 0

        while remaining > 0:
            to_read = chunk_size if remaining > chunk_size else remaining
            chunk = self.ser.read(to_read)
            if chunk:
                self.received_data.extend(chunk)
                got += len(chunk)
                remaining -= len(chunk)
                last_data_time = time.time()

                if nbytes >= 10000:  # log cada ~10%
                    progress = int((got / nbytes) * 100)
                    if progress - last_progress >= 10:
                        logging.info(f"📊 Progreso{(' ' + log_label) if log_label else ''}: {got}/{nbytes} bytes ({progress}%)")
                        last_progress = progress
            else:
                if time.time() - last_data_time > inactivity_timeout:
                    logging.error(f"❌ Timeout sin datos (recibido {got}/{nbytes})")
                    return False
        return True

    def receive_image_simple(self, file_size, save_path=None):
        """Recepción CONFIABLE por tamaño exacto (ignora marcadores en el stream)."""
        try:
            logging.info("📥 Recepción simple iniciada...")

            # 1) Esperar inicio
            if not self._wait_start_marker(max_wait=30):
                return False

            # 2) Leer 4 bytes de tamaño (big-endian)
            size_data = b''
            size_deadline = time.time() + 10
            while len(size_data) < SIZE_BYTES and time.time() < size_deadline:
                chunk = self.ser.read(SIZE_BYTES - len(size_data))
                if chunk:
                    size_data += chunk
            if len(size_data) != SIZE_BYTES:
                logging.error("❌ No se pudieron leer 4 bytes de tamaño")
                return False

            transmitted_size = struct.unpack('>I', size_data)[0]
            logging.info(f"📊 Bytes de tamaño: {size_data.hex()}")
            logging.info(f"📊 Tamaño transmitido: {transmitted_size} bytes")
            logging.info(f"📊 Tamaño esperado: {file_size} bytes")

            # Diferencia tolerable (aviso)
            if abs(transmitted_size - file_size) > max(1024, int(file_size * 0.1)):
                logging.warning("⚠️ Diferencia inusual entre tamaño ASCII y binario")

            # 3) Leer exactamente transmitted_size bytes
            self.received_data = bytearray()
            ok = self._read_exact(transmitted_size, inactivity_timeout=30, chunk_size=4096, log_label="")
            if not ok:
                return False

            logging.info(f"✅ Tamaño completo recibido: {len(self.received_data)} bytes")

            # 4) Drenar posible cola (p. ej. \xBB*10 o <FIN>) sin usarla para decidir
            try:
                original_timeout = self.ser.timeout
                self.ser.timeout = 0.05
                extra = self.ser.read(self.ser.in_waiting or 0)
                if extra:
                    logging.debug(f"🔚 Cola drenada ({len(extra)} bytes)")
            finally:
                self.ser.timeout = original_timeout

            # 5) Chequeos JPEG (solo advertencias)
            if not (len(self.received_data) >= 2 and self.received_data[0] == 0xFF and self.received_data[1] == 0xD8):
                logging.warning("⚠️ No se detecta cabecera JPEG (FFD8)")
            if not (len(self.received_data) >= 2 and self.received_data[-2] == 0xFF and self.received_data[-1] == 0xD9):
                logging.warning("⚠️ No se detecta fin JPEG (FFD9)")

            # 6) Guardar
            if not save_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"imagen_{timestamp}.jpg"

            with open(save_path, 'wb') as f:
                f.write(self.received_data)

            logging.info(f"💾 Imagen guardada: {save_path}")
            return True

        except Exception as e:
            logging.error(f"❌ Error recepción: {e}")
            return False

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.close()
                logging.info("🔌 Conexion cerrada")
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description='Cliente UART v4.1 - Recepción por tamaño exacto')
    parser.add_argument('port', help='Puerto serial (ej: /dev/serial0)')
    parser.add_argument('--resp-timeout', type=int, default=45, help='Tiempo máx. para OK|size (seg)')
    parser.add_argument('--resolution', '-r', default='HD_READY',
                        help='Resolución: ULTRA_WIDE, FULL_HD, HD_READY, LOW_LIGHT, THUMBNAIL')
    parser.add_argument('--output', '-o', help='Ruta donde guardar la imagen')
    parser.add_argument('--baudrate', '-b', type=int, default=57600, help='Baud rate')
    parser.add_argument('--rtscts', action='store_true', help='Habilitar RTS/CTS (hardware flow control)')
    parser.add_argument('--xonxoff', action='store_true', help='Habilitar XON/XOFF (software flow control)')

    args = parser.parse_args()

    print("=" * 60)
    print("Cliente UART v4.1 - Recepción por tamaño exacto")
    print("=" * 60)

    client = UARTPhotoClient(
        port=args.port,
        baudrate=args.baudrate,
        timeout=8,
        rtscts=args.rtscts,
        xonxoff=args.xonxoff
    )

    try:
        if not client.connect():
            logging.error("❌ Error conectando")
            return

        time.sleep(0.5)

        if not client.send_command(args.resolution.upper()):
            logging.error("❌ Error enviando comando")
            return

        response = client.wait_for_response()
        if not response:
            logging.error("❌ No se recibió respuesta")
            return
        if not response.startswith(RESP_OK):
            logging.error(f"❌ Error del servidor: {response}")
            return

        # Extraer tamaño ASCII del OK|size (informativo)
        try:
            file_size_ascii = int(response.split("|")[1])
            logging.info(f"📊 Tamaño esperado: {file_size_ascii} bytes")
        except Exception:
            logging.warning("⚠️ No se pudo parsear tamaño ASCII de la respuesta")
            file_size_ascii = 0

        success = client.receive_image_simple(file_size_ascii, args.output)

        if success:
            logging.info("=" * 60)
            logging.info("✅ PROCESO COMPLETO EXITOSO")
            logging.info("=" * 60)
        else:
            logging.error("=" * 60)
            logging.error("❌ ERROR EN EL PROCESO")
            logging.error("=" * 60)

    except KeyboardInterrupt:
        logging.info("\n🛑 Cliente detenido por usuario")
    except Exception as e:
        logging.error(f"❌ Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
