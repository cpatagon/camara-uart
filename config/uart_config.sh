#!/usr/bin/env bash
# Configuración estándar para UART en Raspberry Pi
# 57600 8N1, sin paridad, con RTS/CTS, sin XON/XOFF

PORT="/dev/serial0"
BAUD=57600

echo "[+] Configurando UART en $PORT a $BAUD baudios..."

# Aplicar configuración
sudo stty -F "$PORT" $BAUD cs8 -cstopb -parenb crtscts -ixon -ixoff

# Mostrar configuración relevante
stty -F "$PORT" -a | grep -E "speed|cs|cstopb|parenb|crtscts|ixon|ixoff"
