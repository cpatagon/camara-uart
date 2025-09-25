#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_uart_server.py - Test básico de servidor UART
Funciones: Escucha comandos y responde con confirmaciones
"""

import serial
import time
import sys
import argparse
from datetime import datetime

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] SERVER: {msg}")

def test_uart_server(port="/dev/serial0", baud=57600, timeout=2):
    log(f"🚀 Iniciando servidor de test UART en {port} @ {baud}")
    
    try:
        # Configurar puerto serial
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout,
            rtscts=True,  # RTS/CTS por defecto
            xonxoff=False
        )
        
        # Limpiar buffers
        for _ in range(3):
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)
        
        log(f"✅ Puerto configurado: {ser}")
        log("🟢 Esperando comandos del cliente...")
        log("💡 Comandos disponibles: PING, ECHO, DATA, QUIT")
        
        message_count = 0
        
        while True:
            try:
                # Leer línea del cliente
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if not line:
                    continue
                    
                message_count += 1
                log(f"📨 Recibido #{message_count}: '{line}'")
                
                # Procesar comandos
                if line.upper() == "PING":
                    response = "PONG"
                    ser.write(f"{response}\r\n".encode('utf-8'))
                    log(f"📤 Respondido: {response}")
                    
                elif line.upper().startswith("ECHO"):
                    # Eco del mensaje
                    echo_text = line[5:] if len(line) > 5 else "VACIO"
                    response = f"ECO: {echo_text}"
                    ser.write(f"{response}\r\n".encode('utf-8'))
                    log(f"📤 Eco enviado: {response}")
                    
                elif line.upper() == "DATA":
                    # Enviar datos de prueba
                    test_data = f"DATOS_PRUEBA_{message_count}_{datetime.now().strftime('%H%M%S')}"
                    ser.write(f"{test_data}\r\n".encode('utf-8'))
                    log(f"📤 Datos enviados: {test_data}")
                    
                elif line.upper() == "STATUS":
                    # Enviar status del servidor
                    status = f"OK|MSGS:{message_count}|TIME:{datetime.now().strftime('%H:%M:%S')}"
                    ser.write(f"{status}\r\n".encode('utf-8'))
                    log(f"📤 Status enviado: {status}")
                    
                elif line.upper() == "QUIT":
                    response = "BYE"
                    ser.write(f"{response}\r\n".encode('utf-8'))
                    log(f"📤 Despedida enviada: {response}")
                    log("🛑 Cliente solicitó terminar")
                    break
                    
                else:
                    # Comando desconocido
                    response = f"UNKNOWN_CMD: {line}"
                    ser.write(f"{response}\r\n".encode('utf-8'))
                    log(f"⚠️ Comando desconocido: {line}")
                
                ser.flush()
                time.sleep(0.1)  # Pequeña pausa entre respuestas
                
            except UnicodeDecodeError:
                log("⚠️ Error decodificando mensaje recibido")
            except serial.SerialException as e:
                log(f"❌ Error serial: {e}")
                break
            except KeyboardInterrupt:
                log("🛑 Interrumpido por usuario")
                break
                
    except Exception as e:
        log(f"❌ Error configurando puerto: {e}")
        return False
        
    finally:
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                log("🔌 Puerto cerrado")
        except:
            pass
    
    log(f"📊 Sesión terminada. Mensajes procesados: {message_count}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Test básico de servidor UART")
    parser.add_argument('--port', '-p', default='/dev/serial0', help='Puerto serial')
    parser.add_argument('--baud', '-b', type=int, default=57600, help='Velocidad')
    parser.add_argument('--timeout', '-t', type=int, default=2, help='Timeout lectura')
    parser.add_argument('--no-rts', action='store_true', help='Deshabilitar RTS/CTS')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 TEST SERVIDOR UART")
    print("=" * 60)
    print(f"Puerto: {args.port}")
    print(f"Velocidad: {args.baud} baud")
    print(f"Control flujo: {'Deshabilitado' if args.no_rts else 'RTS/CTS'}")
    print(f"Timeout: {args.timeout}s")
    print("=" * 60)
    print()
    
    # Configurar RTS/CTS según argumentos
    if args.no_rts:
        import serial
        # Monkey patch para deshabilitar RTS/CTS en la función
        original_serial = serial.Serial
        def patched_serial(*a, **kw):
            kw['rtscts'] = False
            kw['xonxoff'] = True  # Usar XON/XOFF en su lugar
            return original_serial(*a, **kw)
        serial.Serial = patched_serial
    
    try:
        success = test_uart_server(args.port, args.baud, args.timeout)
        if success:
            print("\n✅ Test de servidor completado exitosamente")
        else:
            print("\n❌ Test de servidor falló")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrumpido por usuario")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
