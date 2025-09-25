# Esquemas de Conexión UART

## 🔌 Conexiones UART entre Raspberry Pi

### Configuración Básica (Solo Datos)

```
┌─────────────────────────┐         ┌─────────────────────────┐
│    Raspberry Pi         │         │    Raspberry Pi         │
│    SERVIDOR             │         │    CLIENTE              │
│   (camaraN1)            │         │   (raspberrypi)         │
│                         │         │                         │
│  Pin 8  (GPIO14/TXD) ●──┼─────────┼──● Pin 10 (GPIO15/RXD) │
│  Pin 10 (GPIO15/RXD) ●──┼─────────┼──● Pin 8  (GPIO14/TXD) │
│  Pin 6  (GND)        ●──┼─────────┼──● Pin 6  (GND)        │
│                         │         │                         │
└─────────────────────────┘         └─────────────────────────┘
```

### Configuración Completa (Datos + Control de Flujo)

```
┌─────────────────────────┐         ┌─────────────────────────┐
│    Raspberry Pi         │         │    Raspberry Pi         │
│    SERVIDOR             │         │    CLIENTE              │
│   (camaraN1)            │         │   (raspberrypi)         │
│                         │         │                         │
│  Pin 8  (GPIO14/TXD) ●──┼─────────┼──● Pin 10 (GPIO15/RXD) │
│  Pin 10 (GPIO15/RXD) ●──┼─────────┼──● Pin 8  (GPIO14/TXD) │
│  Pin 6  (GND)        ●──┼─────────┼──● Pin 6  (GND)        │
│                         │         │                         │
│  Pin 11 (GPIO17/RTS) ●──┼─────────┼──● Pin 36 (GPIO16/CTS) │
│  Pin 36 (GPIO16/CTS) ●──┼─────────┼──● Pin 11 (GPIO17/RTS) │
│                         │         │                         │
└─────────────────────────┘         └─────────────────────────┘
```

## 📋 Tabla de Conexiones

### Conexiones Mínimas (Requeridas)

| Función | Raspberry Pi Servidor | Raspberry Pi Cliente | Cable      |
|---------|----------------------|---------------------|------------|
| **TX→RX** | Pin 8 (GPIO14/TXD)   | Pin 10 (GPIO15/RXD) | Datos →    |
| **RX←TX** | Pin 10 (GPIO15/RXD)  | Pin 8 (GPIO14/TXD)  | Datos ←    |
| **GND**   | Pin 6 (GND)          | Pin 6 (GND)         | Común      |

### Conexiones Opcionales (Control de Flujo Hardware)

| Función   | Raspberry Pi Servidor | Raspberry Pi Cliente | Propósito           |
|-----------|----------------------|---------------------|---------------------|
| **RTS→CTS** | Pin 11 (GPIO17/RTS)  | Pin 36 (GPIO16/CTS) | Control de flujo →  |
| **CTS←RTS** | Pin 36 (GPIO16/CTS)  | Pin 11 (GPIO17/RTS) | Control de flujo ←  |

## 🎯 Vista de Pines GPIO

```
Raspberry Pi Header (40 pines)
     3V3  (1) (2)  5V
   GPIO2  (3) (4)  5V
   GPIO3  (5) (6)  GND ●────────────── GND Común
   GPIO4  (7) (8)  GPIO14/TXD ●────── TX → RX
     GND  (9) (10) GPIO15/RXD ●────── RX ← TX
  GPIO17 (11) (12) GPIO18
  GPIO27 (13) (14) GND
  GPIO22 (15) (16) GPIO23
     3V3 (17) (18) GPIO24
  GPIO10 (19) (20) GND
   GPIO9 (21) (22) GPIO25
  GPIO11 (23) (24) GPIO8
     GND (25) (26) GPIO7
   GPIO0 (27) (28) GPIO1
   GPIO5 (29) (30) GND
   GPIO6 (31) (32) GPIO12
  GPIO13 (33) (34) GND
  GPIO19 (35) (36) GPIO16/CTS ●───── CTS ↔ RTS
  GPIO26 (37) (38) GPIO20
     GND (39) (40) GPIO21

● = Conexiones requeridas (pines 6, 8, 10)
● = Conexiones opcionales (pines 11, 36)
```

## ⚡ Especificaciones Técnicas

- **Niveles lógicos**: 3.3V TTL
- **Velocidades soportadas**: 9600 - 115200 bps (recomendado: 57600)
- **Protocolo**: 8 bits de datos, 1 bit de parada, sin paridad (8N1)
- **Control de flujo**: RTS/CTS (hardware) o XON/XOFF (software)

## 🔧 Configuración de Hardware

### Activar UART en `/boot/firmware/config.txt`:
```bash
# Configuración básica
enable_uart=1
dtoverlay=uart0

# Para habilitar RTS/CTS (control de flujo hardware)
dtoverlay=uart0,ctsrts
```

### Deshabilitar getty:
```bash
sudo systemctl disable --now serial-getty@ttyS0.service
```

## 🚨 Advertencias Importantes

1. **Nunca cruces 5V con 3.3V** - Ambas RPi usan 3.3V
2. **Verifica las conexiones** antes de energizar
3. **GND común es obligatorio** - Sin él no hay comunicación
4. **TX va a RX, RX va a TX** - Las líneas se cruzan
5. **RTS/CTS también se cruzan** entre dispositivos

## 🧪 Test de Conectividad

```bash
# RPi Servidor - Monitorear:
cat /dev/serial0 &

# RPi Cliente - Enviar:
echo "TEST_CONEXION" > /dev/serial0

# Si aparece "TEST_CONEXION" en el servidor → ✅ Funciona
# Si no aparece → ❌ Revisar conexiones
```

## 🔄 Loopback Virtual (Testing con una sola RPi)

```
┌─────────────────────────────────────────────┐
│           Raspberry Pi única                │
│                                             │
│  ┌─────────────┐    socat    ┌─────────────┐ │
│  │   Servidor  │◄───────────►│   Cliente   │ │
│  │/tmp/server  │             │/tmp/client  │ │
│  └─────────────┘             └─────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

### Comando para loopback virtual:
```bash
socat PTY,link=/tmp/server_uart,raw,echo=0 PTY,link=/tmp/client_uart,raw,echo=0 &
```

## 📖 Ejemplos de Configuración

### Sin Control de Flujo:
```bash
# Servidor
./init.sh server --port /dev/serial0 --baud 57600 --sleep-ms 2

# Cliente  
./init.sh client --port /dev/serial0 --baud 57600
```

### Con RTS/CTS:
```bash
# Servidor
./init.sh server --port /dev/serial0 --baud 57600 --rtscts

# Cliente
./init.sh client --port /dev/serial0 --baud 57600 --rtscts
```

### Con XON/XOFF:
```bash
# Servidor
./init.sh server --port /dev/serial0 --baud 57600 --xonxoff

# Cliente
./init.sh client --port /dev/serial0 --baud 57600 --xonxoff
```
