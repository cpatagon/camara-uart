#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente UART - Con protocolo ACK bidireccional
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
SIZE_BYTES = 4

# Protocolo ACK
ACK_READY = "ACK_READY"
ACK_OK = "ACK_OK"
ACK_MISSING = "ACK_MISSING:"
ACK_ERROR = "ACK_ERROR"

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
        """Conectar con configuración"""
        try:
            # Preparación opcional del puerto
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
                timeout=self.timeout,
                write_timeout=2,
                rtscts=self.rtscts,
                xonxoff=self.xonxoff
            )

            # Limpieza inicial extendida
            for _ in range(5):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)

            logging.info(f"✅ Cliente: {self.port} @ {self.baudrate} (rtscts={self.rtscts}, xonxoff={self.xonxoff})")
            return True

        except Exception as e:
            logging.error(f"❌ Error conexión: {e}")
            return False

    def send_command(self, resolution="THUMBNAIL"):
        """Enviar comando con limpieza previa"""
        try:
            cmd = f"{CMD_BEGIN}{CMD_START}{{size_name:{resolution}}}{CMD_END}\r\n"
            logging.info(f"📤 Enviando comando: {cmd.strip()}")

            # Limpieza más agresiva
            for _ in range(3):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)

            self.ser.write(cmd.encode('utf-8'))
            self.ser.flush()
            logging.info("✅ Comando enviado")
            time.sleep(1.0)
            return True
        except Exception as e:
            logging.error(f"❌ Error enviando: {e}")
            return False

    def wait_for_response(self, timeout_s=None):
        """Esperar respuesta con timeout extendido"""
        if timeout_s is None:
            timeout_s = TIMEOUT_RESP
        end = time.time() + timeout_s
        
        while time.time() < end:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line and (line.startswith(RESP_OK) or line.startswith(RESP_BAD)):
                    logging.info(f"✅ Respuesta: {line}")
                    return line
            except Exception as e:
                logging.debug(f"Error leyendo respuesta: {e}")
                continue
                
        logging.warning("⏱️ Timeout esperando respuesta")
        return None

    def send_client_ready(self):
        """Informar al servidor que estamos listos para recibir"""
        try:
            msg = f"{ACK_READY}\r\n"
            self.ser.write(msg.encode('utf-8'))
            self.ser.flush()
            logging.info("📋 Informamos al servidor: cliente listo")
            return True
        except Exception as e:
            logging.error(f"❌ Error enviando ready: {e}")
            return False

    def send_ack_status(self, received_bytes: int, expected_bytes: int):
        """Enviar estado ACK al servidor"""
        try:
            if received_bytes == expected_bytes:
                msg = f"{ACK_OK}\r\n"
                logging.info(f"✅ Enviando ACK_OK: {received_bytes} bytes recibidos correctamente")
            else:
                msg = f"{ACK_MISSING}:{received_bytes}\r\n"
                missing = expected_bytes - received_bytes
                logging.warning(f"⚠️ Enviando ACK_MISSING: faltan {missing} bytes (recibido {received_bytes}/{expected_bytes})")
            
            self.ser.write(msg.encode('utf-8'))
            self.ser.flush()
            return True
        except Exception as e:
            logging.error(f"❌ Error enviando ACK: {e}")
            try:
                self.ser.write(f"{ACK_ERROR}\r\n".encode('utf-8'))
                self.ser.flush()
            except:
                pass
            return False

    def _wait_start_marker(self, max_wait=45):
        """Esperar marcador de inicio con timeout extendido"""
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
                
            # Detectar marcador de retransmisión
            if len(window) >= 4 and window[-4:] == b"\xCC" * 4:
                logging.info("🔄 Detectado marcador de retransmisión")
                return "retry"
                
        logging.error("❌ No se encontró marcador de inicio")
        return False

    def _read_exact(self, nbytes, inactivity_timeout=45, chunk_size=4096):
        """Lectura exacta con manejo de retransmisiones"""
        remaining = nbytes
        last_data_time = time.time()
        got = 0
        last_progress = 0

        while remaining > 0:
            # Detectar posible retransmisión mirando bytes disponibles
            if self.ser.in_waiting >= 4:
                # Leer 4 bytes para verificar si es marcador de retransmisión
                potential_marker = self.ser.read(4)
                if potential_marker == b"\xCC" * 4:
                    logging.info("🔄 Retransmisión detectada durante lectura")
                    continue
                else:
                    # No era marcador, agregar estos bytes a los datos
                    self.received_data.extend(potential_marker)
                    got += len(potential_marker)
                    remaining -= len(potential_marker)
                    last_data_time = time.time()

            to_read = min(chunk_size, remaining)
            chunk = self.ser.read(to_read)
            
            if chunk:
                self.received_data.extend(chunk)
                got += len(chunk)
                remaining -= len(chunk)
                last_data_time = time.time()

                # Log de progreso mejorado
                if nbytes >= 10000:
                    progress = int((got / nbytes) * 100)
                    if progress - last_progress >= 10:
                        logging.info(f"📊 Progreso: {got}/{nbytes} bytes ({progress}%)")
                        last_progress = progress
            else:
                # Verificar timeout por inactividad
                if time.time() - last_data_time > inactivity_timeout:
                    logging.error(f"❌ Timeout sin datos (recibido {got}/{nbytes})")
                    return False
                    
        return True

    def receive_image(self, expected_size, save_path=None, enable_ack=True):
        """Recepción con protocolo ACK completo"""
        try:
            logging.info("📥 Iniciando recepción ...")

            # 1. Opcional: Informar que estamos listos
            if enable_ack:
                self.send_client_ready()
                time.sleep(0.5)

            # 2. Esperar marcador de inicio
            start_result = self._wait_start_marker(max_wait=60)
            if start_result == False:
                return False
            elif start_result == "retry":
                logging.info("🔄 Iniciando desde retransmisión")

            # 3. Leer tamaño transmitido
            size_data = b''
            size_deadline = time.time() + 15
            while len(size_data) < SIZE_BYTES and time.time() < size_deadline:
                chunk = self.ser.read(SIZE_BYTES - len(size_data))
                if chunk:
                    size_data += chunk

            if len(size_data) != SIZE_BYTES:
                logging.error("❌ No se pudieron leer 4 bytes de tamaño")
                if enable_ack:
                    self.send_ack_status(0, expected_size)
                return False

            transmitted_size = struct.unpack('>I', size_data)[0]
            logging.info(f"📊 Tamaño transmitido: {transmitted_size} bytes")
            logging.info(f"📊 Tamaño esperado: {expected_size} bytes")

            # 4. Recepción principal
            self.received_data = bytearray()
            success = self._read_exact(transmitted_size, inactivity_timeout=60)
            
            if not success:
                if enable_ack:
                    self.send_ack_status(len(self.received_data), expected_size)
                return False

            received_bytes = len(self.received_data)
            logging.info(f"✅ Recepción completada: {received_bytes} bytes")

            # 5. Drenaje de cola final (marcadores)
            try:
                original_timeout = self.ser.timeout
                self.ser.timeout = 1.0  # Timeout más largo para marcadores
                extra = bytearray()
                
                # Leer hasta encontrar marcadores finales o timeout
                while True:
                    chunk = self.ser.read(100)
                    if not chunk:
                        break
                    extra.extend(chunk)
                    
                    # Buscar marcadores finales
                    if b"<FIN_TRANSMISION>" in extra:
                        logging.info("🏁 Marcadores finales detectados")
                        break
                
                if extra:
                    logging.info(f"🔚 Drenado: {len(extra)} bytes de cola final")
                    
            except Exception as e:
                logging.debug(f"Error drenando cola: {e}")
            finally:
                self.ser.timeout = original_timeout

            # 6. Validación JPEG
            jpeg_valid = True
            if not (len(self.received_data) >= 2 and self.received_data[0] == 0xFF and self.received_data[1] == 0xD8):
                logging.warning("⚠️ Sin cabecera JPEG (FFD8)")
                jpeg_valid = False
            if not (len(self.received_data) >= 2 and self.received_data[-2] == 0xFF and self.received_data[-1] == 0xD9):
                logging.warning("⚠️ Sin fin JPEG (FFD9)")
                jpeg_valid = False

            # 7. Envío de ACK final
            if enable_ack:
                # Pausa para asegurar que el servidor esté esperando ACK
                time.sleep(1.0)
                self.send_ack_status(received_bytes, expected_size)

            # 8. Guardar archivo
            if not save_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"imagen{timestamp}.jpg"

            with open(save_path, 'wb') as f:
                f.write(self.received_data)

            logging.info(f"💾 Imagen guardada: {save_path}")
            
            # Resultado final
            success_final = received_bytes == expected_size and jpeg_valid
            if success_final:
                logging.info("🎉 RECEPCIÓN EXITOSA")
            else:
                logging.warning("⚠️ Recepción completada con advertencias")
                
            return success_final

        except Exception as e:
            logging.error(f"❌ Error en recepción: {e}")
            if enable_ack:
                try:
                    self.send_ack_status(len(self.received_data) if hasattr(self, 'received_data') else 0, expected_size)
                except:
                    pass
            return False

    def close(self):
        """Cierre"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.close()
                logging.info("🔌 Cliente cerrado")
        except Exception as e:
            logging.debug(f"Error cerrando cliente: {e}")

def main():
    parser = argparse.ArgumentParser(description='Cliente UART con protocolo ACK')
    parser.add_argument('port', help='Puerto serial')
    parser.add_argument('--resp-timeout', type=int, default=60, help='Timeout para respuesta del servidor')
    parser.add_argument('--resolution', '-r', default='HD_READY', help='Resolución de imagen')
    parser.add_argument('--output', '-o', help='Archivo de salida')
    parser.add_argument('--baudrate', '-b', type=int, default=57600, help='Velocidad')
    parser.add_argument('--rtscts', action='store_true', help='RTS/CTS flow control')
    parser.add_argument('--xonxoff', action='store_true', help='XON/XOFF flow control')
    parser.add_argument('--no-ack', action='store_true', help='Deshabilitar protocolo ACK')

    args = parser.parse_args()
    enable_ack = not args.no_ack
    resp_timeout = int(os.environ.get('RESP_TIMEOUT', args.resp_timeout))

    print("=" * 70)
    print("Cliente UART con protocolo ACK bidireccional")
    print("=" * 70)

    client = UARTPhotoClient(
        port=args.port,
        baudrate=args.baudrate,
        timeout=10,  # Timeout más largo
        rtscts=args.rtscts,
        xonxoff=args.xonxoff
    )

    try:
        if not client.connect():
            logging.error("❌ Error conectando")
            return

        time.sleep(1.0)  # Pausa inicial más larga

        if not client.send_command(args.resolution.upper()):
            logging.error("❌ Error enviando comando")
            return

        response = client.wait_for_response(timeout_s=resp_timeout)
        if not response:
            logging.error("❌ No se recibió respuesta del servidor")
            return
        if not response.startswith(RESP_OK):
            logging.error(f"❌ Error del servidor: {response}")
            return

        # Extraer tamaño esperado
        try:
            expected_size = int(response.split("|")[1])
            logging.info(f"📊 Tamaño esperado según servidor: {expected_size} bytes")
        except Exception:
            logging.warning("⚠️ No se pudo parsear tamaño de respuesta")
            expected_size = 0

        # Recepción  con ACK
        success = client.receive_image(expected_size, args.output, enable_ack=enable_ack)

        if success:
            logging.info("=" * 70)
            logging.info("🎉 ¡PROCESO COMPLETADO CON ÉXITO!")
            logging.info("=" * 70)
        else:
            logging.error("=" * 70)
            logging.error("❌ ERROR EN EL PROCESO")
            logging.error("=" * 70)

    except KeyboardInterrupt:
        logging.info("\n🛑 Cliente detenido por usuario")
    except Exception as e:
        logging.error(f"❌ Error crítico: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
