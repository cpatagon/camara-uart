#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_uart_client.py - Test básico de cliente UART
Funciones: Envía comandos y verifica respuestas del servidor
"""

import serial
import time
import sys
import argparse
from datetime import datetime

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] CLIENT: {msg}")

def send_command(ser, command, expect_response=True, timeout=5):
    """Enviar comando y esperar respuesta"""
    try:
        # Limpiar buffer de entrada
        ser.reset_input_buffer()
        
        # Enviar comando
        ser.write(f"{command}\r\n".encode('utf-8'))
        ser.flush()
        log(f"📤 Enviado: '{command}'")
        
        if not expect_response:
            return True, "No response expected"
        
        # Esperar respuesta
        start_time = time.time()
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:
                response = ser.readline().decode('utf-8', errors='ignore').strip()
                if response:
                    log(f"📨 Recibido: '{response}'")
                    return True, response
            time.sleep(0.1)
        
        log(f"⏰ Timeout esperando respuesta a '{command}'")
        return False, "TIMEOUT"
        
    except Exception as e:
        log(f"❌ Error enviando '{command}': {e}")
        return False, str(e)

def test_uart_client(port="/dev/serial0", baud=57600, timeout=2):
    log(f"🚀 Iniciando cliente de test UART en {port} @ {baud}")
    
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
        log("🧪 Iniciando secuencia de tests...")
        
        tests_passed = 0
        tests_total = 0
        
        # Test 1: PING-PONG básico
        log("\n🧪 TEST 1: Ping-Pong básico")
        tests_total += 1
        success, response = send_command(ser, "PING")
        if success and response.upper() == "PONG":
            log("✅ Test 1 PASADO: Ping-Pong funcional")
            tests_passed += 1
        else:
            log(f"❌ Test 1 FALLADO: Esperaba 'PONG', recibió '{response}'")
        
        time.sleep(0.5)
        
        # Test 2: ECHO con datos
        log("\n🧪 TEST 2: Echo con datos")
        tests_total += 1
        test_message = f"Hola_Mundo_{datetime.now().strftime('%H%M%S')}"
        success, response = send_command(ser, f"ECHO {test_message}")
        if success and test_message in response:
            log("✅ Test 2 PASADO: Echo funcional")
            tests_passed += 1
        else:
            log(f"❌ Test 2 FALLADO: No se encontró '{test_message}' en '{response}'")
        
        time.sleep(0.5)
        
        # Test 3: Solicitar datos del servidor
        log("\n🧪 TEST 3: Solicitud de datos")
        tests_total += 1
        success, response = send_command(ser, "DATA")
        if success and "DATOS_PRUEBA" in response:
            log("✅ Test 3 PASADO: Datos recibidos del servidor")
            tests_passed += 1
        else:
            log(f"❌ Test 3 FALLADO: Datos no recibidos correctamente: '{response}'")
        
        time.sleep(0.5)
        
        # Test 4: Status del servidor
        log("\n🧪 TEST 4: Status del servidor")
        tests_total += 1
        success, response = send_command(ser, "STATUS")
        if success and "OK|" in response and "MSGS:" in response:
            log("✅ Test 4 PASADO: Status recibido correctamente")
            tests_passed += 1
        else:
            log(f"❌ Test 4 FALLADO: Status incorrecto: '{response}'")
        
        time.sleep(0.5)
        
        # Test 5: Comando desconocido
        log("\n🧪 TEST 5: Comando desconocido")
        tests_total += 1
        success, response = send_command(ser, "COMANDO_INEXISTENTE")
        if success and "UNKNOWN_CMD" in response:
            log("✅ Test 5 PASADO: Manejo correcto de comando desconocido")
            tests_passed += 1
        else:
            log(f"❌ Test 5 FALLADO: Respuesta inesperada: '{response}'")
        
        time.sleep(0.5)
        
        # Test 6: Múltiples comandos rápidos
        log("\n🧪 TEST 6: Múltiples comandos rápidos")
        tests_total += 1
        rapid_success = 0
        for i in range(3):
            success, response = send_command(ser, f"ECHO Test_Rapido_{i}", timeout=3)
            if success and f"Test_Rapido_{i}" in response:
                rapid_success += 1
            time.sleep(0.2)
        
        if rapid_success >= 2:  # Al menos 2 de 3 deben pasar
            log("✅ Test 6 PASADO: Comandos rápidos manejados correctamente")
            tests_passed += 1
        else:
            log(f"❌ Test 6 FALLADO: Solo {rapid_success}/3 comandos rápidos exitosos")
        
        time.sleep(1)
        
        # Finalizar sesión
        log("\n🛑 Finalizando sesión...")
        send_command(ser, "QUIT", timeout=3)
        
        # Resumen de resultados
        log(f"\n📊 RESUMEN DE TESTS:")
        log(f"   ✅ Tests pasados: {tests_passed}/{tests_total}")
        log(f"   ❌ Tests fallados: {tests_total - tests_passed}/{tests_total}")
        
        success_rate = (tests_passed / tests_total) * 100
        log(f"   📈 Tasa de éxito: {success_rate:.1f}%")
        
        if tests_passed == tests_total:
            log("🎉 ¡TODOS LOS TESTS PASARON! Comunicación UART excelente")
            return True
        elif tests_passed >= tests_total * 0.8:  # 80% o más
            log("✅ Tests mayormente exitosos. Comunicación UART funcional")
            return True
        else:
            log("❌ Múltiples tests fallaron. Revisar configuración UART")
            return False
            
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

def interactive_mode(port, baud, timeout):
    """Modo interactivo para enviar comandos manualmente"""
    log("🎮 Modo interactivo activado")
    log("💡 Comandos: PING, ECHO <texto>, DATA, STATUS, QUIT")
    log("💡 Escribe 'exit' para salir")
    
    try:
        ser = serial.Serial(
            port=port, baudrate=baud, timeout=timeout,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS, rtscts=True, xonxoff=False
        )
        
        for _ in range(3):
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)
        
        log(f"✅ Puerto configurado para modo interactivo")
        
        while True:
            try:
                command = input("\n🎮 Comando: ").strip()
                if not command:
                    continue
                if command.lower() in ['exit', 'quit', 'salir']:
                    send_command(ser, "QUIT", timeout=3)
                    break
                
                success, response = send_command(ser, command, timeout=5)
                if not success:
                    log("⚠️ No se recibió respuesta válida")
                    
            except KeyboardInterrupt:
                log("\n🛑 Modo interactivo interrumpido")
                break
                
    except Exception as e:
        log(f"❌ Error en modo interactivo: {e}")
    finally:
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                log("🔌 Puerto cerrado")
        except:
            pass

def main():
    parser = argparse.ArgumentParser(description="Test básico de cliente UART")
    parser.add_argument('--port', '-p', default='/dev/serial0', help='Puerto serial')
    parser.add_argument('--baud', '-b', type=int, default=57600, help='Velocidad')
    parser.add_argument('--timeout', '-t', type=int, default=3, help='Timeout lectura')
    parser.add_argument('--no-rts', action='store_true', help='Deshabilitar RTS/CTS')
    parser.add_argument('--interactive', '-i', action='store_true', help='Modo interactivo')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 TEST CLIENTE UART")
    print("=" * 60)
    print(f"Puerto: {args.port}")
    print(f"Velocidad: {args.baud} baud")
    print(f"Control flujo: {'Deshabilitado' if args.no_rts else 'RTS/CTS'}")
    print(f"Timeout: {args.timeout}s")
    print(f"Modo: {'Interactivo' if args.interactive else 'Automático'}")
    print("=" * 60)
    print()
    
    # Configurar RTS/CTS según argumentos
    if args.no_rts:
        import serial
        original_serial = serial.Serial
        def patched_serial(*a, **kw):
            kw['rtscts'] = False
            kw['xonxoff'] = True
            return original_serial(*a, **kw)
        serial.Serial = patched_serial
    
    try:
        if args.interactive:
            interactive_mode(args.port, args.baud, args.timeout)
        else:
            success = test_uart_client(args.port, args.baud, args.timeout)
            if success:
                print("\n🎉 ¡TEST DE CLIENTE COMPLETADO EXITOSAMENTE!")
                print("✅ La comunicación UART funciona correctamente")
            else:
                print("\n❌ TEST DE CLIENTE FALLÓ")
                print("⚠️ Revisar configuración UART y conexión")
                sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrumpido por usuario")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
