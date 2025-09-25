#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente UART con diagnóstico avanzado de últimos bytes
"""

import serial
import time
import struct
import logging
import binascii
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class EnhancedUARTClient:
    def __init__(self, port, baudrate=38400, timeout=3, rtscts=False, xonxoff=True):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.rtscts = rtscts
        self.xonxoff = xonxoff
        self.ser = None
        self.received_data = bytearray()
        self.debug_log = []

    def log_debug(self, message):
        """Log con timestamp para análisis posterior"""
        timestamp = time.time()
        self.debug_log.append((timestamp, message))
        logging.info(f"DEBUG: {message}")

    def connect(self):
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

            # Limpieza inicial
            for _ in range(3):
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)

            logging.info(f"Conectado: {self.port} @ {self.baudrate} (rtscts={self.rtscts}, xonxoff={self.xonxoff})")
            return True
        except Exception as e:
            logging.error(f"Error conexión: {e}")
            return False

    def send_command_and_wait_response(self, resolution="HD_READY"):
        """Enviar comando y esperar respuesta"""
        try:
            cmd = f"<FOTO:{{size_name:{resolution}}}>\r\n"
            logging.info(f"Enviando comando: {cmd.strip()}")

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.2)

            self.ser.write(cmd.encode('utf-8'))
            self.ser.flush()
            time.sleep(1.0)

            # Esperar respuesta
            response_line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            logging.info(f"Respuesta recibida: {response_line}")

            if not response_line.startswith("OK|"):
                logging.error(f"Respuesta inválida: {response_line}")
                return None

            expected_size = int(response_line.split("|")[1])
            logging.info(f"Tamaño esperado: {expected_size} bytes")
            return expected_size

        except Exception as e:
            logging.error(f"Error enviando comando: {e}")
            return None

    def find_start_marker(self):
        """Buscar marcador de inicio"""
        start_marker = b'\xAA' * 10
        window = bytearray()
        attempts = 0
        max_attempts = 1000

        logging.info("Buscando marcador de inicio...")

        while attempts < max_attempts:
            b = self.ser.read(1)
            if not b:
                attempts += 1
                continue

            window += b
            if len(window) > len(start_marker):
                window = window[-len(start_marker):]

            if window == start_marker:
                logging.info("Marcador de inicio encontrado")
                return True

            attempts += 1

        logging.error("No se encontró marcador de inicio")
        return False

    def read_size_header(self):
        """Leer cabecera de tamaño (4 bytes)"""
        size_data = b''
        deadline = time.time() + 10

        while len(size_data) < 4 and time.time() < deadline:
            chunk = self.ser.read(4 - len(size_data))
            if chunk:
                size_data += chunk

        if len(size_data) != 4:
            logging.error(f"No se pudieron leer 4 bytes de tamaño: {len(size_data)}")
            return None

        transmitted_size = struct.unpack('>I', size_data)[0]
        logging.info(f"Tamaño transmitido: {transmitted_size} bytes (hex: {size_data.hex()})")
        return transmitted_size

    def receive_with_enhanced_diagnostics(self, expected_size):
        """Recepción con diagnóstico avanzado de últimos bytes"""
        self.received_data = bytearray()
        chunk_size = 4096
        last_activity = time.time()
        consecutive_empty_reads = 0
        recovery_attempts = 0
        max_recovery_attempts = 5

        logging.info(f"Iniciando recepción mejorada de {expected_size} bytes...")

        while len(self.received_data) < expected_size:
            remaining = expected_size - len(self.received_data)
            to_read = min(chunk_size, remaining)

            # Información de estado antes de leer
            buffer_before = self.ser.in_waiting
            time_since_activity = time.time() - last_activity

            chunk = self.ser.read(to_read)

            if chunk:
                self.received_data.extend(chunk)
                last_activity = time.time()
                consecutive_empty_reads = 0
                recovery_attempts = 0

                # Log detallado para últimos 10KB
                if remaining <= 10240:
                    buffer_after = self.ser.in_waiting
                    self.log_debug(f"Últimos {remaining} bytes - recibidos: {len(chunk)}, "
                                 f"buffer: {buffer_before}->{buffer_after}")

                # Log cada 25KB o cuando quedan pocos bytes
                if len(self.received_data) % 25600 == 0 or remaining <= 5120:
                    pct = int(len(self.received_data) * 100 / expected_size)
                    logging.info(f"Progreso: {len(self.received_data)}/{expected_size} ({pct}%) "
                               f"- buffer: {buffer_before}")

            else:
                consecutive_empty_reads += 1
                buffer_current = self.ser.in_waiting

                self.log_debug(f"Sin datos #{consecutive_empty_reads} - "
                             f"inactividad: {time_since_activity:.1f}s - "
                             f"buffer: {buffer_current} - faltan: {remaining}")

                # DIAGNÓSTICO CRÍTICO: cuando quedan pocos bytes
                if remaining <= 2048:
                    self.log_debug(f"CRÍTICO: Solo faltan {remaining} bytes")
                    
                    # Estrategias de recuperación
                    if consecutive_empty_reads >= 10 and recovery_attempts < max_recovery_attempts:
                        recovery_attempts += 1
                        self.log_debug(f"Intento recuperación #{recovery_attempts}")
                        
                        # Estrategia 1: Cambiar timeout temporalmente
                        if recovery_attempts == 1:
                            old_timeout = self.ser.timeout
                            self.ser.timeout = 0.1
                            self.log_debug("Reduciendo timeout a 0.1s")
                            time.sleep(0.5)
                            self.ser.timeout = old_timeout
                            
                        # Estrategia 2: Leer byte a byte
                        elif recovery_attempts == 2:
                            self.log_debug("Cambiando a lectura byte a byte")
                            chunk_size = 1
                            
                        # Estrategia 3: Reset de buffers
                        elif recovery_attempts == 3:
                            self.log_debug("Reseteando buffers")
                            self.ser.reset_input_buffer()
                            time.sleep(0.2)
                            
                        # Estrategia 4: Pausa larga
                        elif recovery_attempts == 4:
                            self.log_debug("Pausa de recuperación 2s")
                            time.sleep(2.0)
                            
                        consecutive_empty_reads = 0

                # Timeout definitivo después de muchos intentos
                if time_since_activity > 15 and consecutive_empty_reads > 50:
                    logging.error(f"Timeout definitivo - recibido {len(self.received_data)}/{expected_size}")
                    break

                time.sleep(0.1)

        bytes_received = len(self.received_data)
        bytes_missing = expected_size - bytes_received

        logging.info(f"RESULTADO: {bytes_received}/{expected_size} bytes - "
                   f"perdidos: {bytes_missing} ({bytes_missing/expected_size*100:.2f}%)")

        return bytes_received == expected_size

    def analyze_final_data(self, expected_size):
        """Análisis detallado de los datos finales"""
        bytes_received = len(self.received_data)
        bytes_missing = expected_size - bytes_received

        print(f"\n=== ANÁLISIS FINAL ===")
        print(f"Esperado: {expected_size} bytes")
        print(f"Recibido: {bytes_received} bytes")
        print(f"Perdido:  {bytes_missing} bytes")

        if bytes_missing > 0:
            print(f"\n=== ANÁLISIS DE PÉRDIDA ===")
            
            # Verificar si hay datos residuales
            self.ser.timeout = 0.1
            extra_data = self.ser.read(2048)
            if extra_data:
                print(f"Datos extra encontrados: {len(extra_data)} bytes")
                print(f"Hex sample: {extra_data[:32].hex()}")
                
                # Intentar agregar datos extra
                self.received_data.extend(extra_data)
                print(f"Total con extras: {len(self.received_data)} bytes")
            else:
                print("No hay datos residuales en buffer")

        # Análisis JPEG
        if bytes_received >= 4:
            if self.received_data[:2] == b'\xff\xd8':
                print("✅ Cabecera JPEG correcta (FFD8)")
            else:
                print(f"❌ Cabecera incorrecta: {self.received_data[:2].hex()}")

            if self.received_data[-2:] == b'\xff\xd9':
                print("✅ Final JPEG correcto (FFD9)")
            else:
                print(f"❌ Final incorrecto: {self.received_data[-4:].hex()}")

        # Guardar archivos de análisis
        timestamp = datetime.now().strftime("%H%M%S")
        
        if self.received_data:
            data_file = f"/tmp/received_data_{timestamp}.jpg"
            with open(data_file, 'wb') as f:
                f.write(self.received_data)
            print(f"Datos guardados: {data_file}")

        # Guardar log de debug
        log_file = f"/tmp/debug_log_{timestamp}.txt"
        with open(log_file, 'w') as f:
            for ts, msg in self.debug_log:
                f.write(f"{ts:.3f}: {msg}\n")
        print(f"Log debug guardado: {log_file}")

        return bytes_received == expected_size

    def run_enhanced_test(self, resolution="HD_READY", output_path=None):
        """Ejecutar test completo con diagnósticos"""
        print("=== CLIENTE DIAGNÓSTICO AVANZADO ===")
        
        if not self.connect():
            return False

        try:
            # Enviar comando y esperar respuesta
            expected_size = self.send_command_and_wait_response(resolution)
            if not expected_size:
                return False

            # Buscar marcador y leer tamaño
            if not self.find_start_marker():
                return False

            transmitted_size = self.read_size_header()
            if not transmitted_size:
                return False

            # Verificar consistencia de tamaños
            if expected_size != transmitted_size:
                logging.warning(f"Diferencia de tamaños: ASCII={expected_size}, binario={transmitted_size}")

            # Recepción con diagnósticos
            success = self.receive_with_enhanced_diagnostics(transmitted_size)

            # Análisis final
            final_success = self.analyze_final_data(transmitted_size)

            # Guardar resultado final si se especifica
            if output_path and self.received_data:
                with open(output_path, 'wb') as f:
                    f.write(self.received_data)
                print(f"Imagen final guardada: {output_path}")

            return final_success

        except Exception as e:
            logging.error(f"Error durante test: {e}")
            return False
        finally:
            if self.ser:
                self.ser.close()

def main():
    parser = argparse.ArgumentParser(description='Cliente diagnóstico avanzado')
    parser.add_argument('port', help='Puerto serial')
    parser.add_argument('--baudrate', '-b', type=int, default=38400)
    parser.add_argument('--resolution', '-r', default='HD_READY')
    parser.add_argument('--output', '-o', help='Archivo de salida')
    parser.add_argument('--rtscts', action='store_true')
    parser.add_argument('--xonxoff', action='store_true', default=True)
    
    args = parser.parse_args()
    
    client = EnhancedUARTClient(
        port=args.port,
        baudrate=args.baudrate,
        rtscts=args.rtscts,
        xonxoff=args.xonxoff
    )
    
    success = client.run_enhanced_test(args.resolution, args.output)
    
    if success:
        print("\n✅ TEST EXITOSO")
    else:
        print("\n❌ TEST FALLÓ")

if __name__ == "__main__":
    main()
