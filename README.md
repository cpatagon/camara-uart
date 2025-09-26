# Sistema Cámara UART — v5 con Protocolo ACK

**Sistema robusto de captura y transmisión de imágenes entre Raspberry Pi con verificación y retransmisión automática**

> Proyecto avanzado para capturar fotos en una Raspberry Pi y transmitirlas por UART con **protocolo ACK**, **verificación de integridad**, y **retransmisión automática** de datos perdidos o corruptos.

---

## 🌟 Características Principales

- **✅ Protocolo ACK**: Verificación automática de recepción completa
- **🔄 Retransmisión inteligente**: Corrección automática de datos perdidos
- **📸 Múltiples resoluciones**: Desde thumbnail hasta ultra-wide
- **🛡️ Transmisión robusta**: Control de flujo por hardware (RTS/CTS) o software (XON/XOFF)
- **🎯 Lectura exacta**: Cliente lee exactamente el tamaño anunciado
- **📊 Desaceleración adaptativa**: Ralentización progresiva en últimos KB para mayor estabilidad
- **🔧 APIs separadas**: Arquitectura modular (captura + transporte)
- **📈 Logging detallado**: Monitoreo completo del proceso

---

## 🔎 Cómo Funciona el Protocolo

### Flujo Completo con ACK:
```
1. Cliente → Servidor: <FOTO:{size_name:HD_READY}>
2. Servidor → Cliente: OK|<size>
3. Servidor → Cliente: 0xAA*10 + size(4B) + JPEG_DATA + marcadores
4. Cliente → Servidor: ACK_OK | ACK_MISSING:<bytes_recibidos>
5. [Si faltan datos] Servidor → Cliente: 0xCC*4 + datos_faltantes
6. Cliente → Servidor: ACK_OK (confirmación final)
```

### Resoluciones Disponibles:
- **THUMBNAIL**: 320×240 (ideal para pruebas rápidas)
- **LOW_LIGHT**: 640×480 (buena relación velocidad/calidad)
- **HD_READY**: 1280×720 (recomendado general)
- **FULL_HD**: 1920×1080 (alta calidad)
- **ULTRA_WIDE**: 4056×3040 (máxima resolución, más lento)

---

## 📋 Componentes del Sistema

### Hardware Requerido:
- **Servidor**: Raspberry Pi Zero W + Raspberry Camera Module 3 Wide
- **Cliente**: Raspberry Pi 3 Model B (o superior)
- **Comunicación**: Conexión UART con cables GPIO

### Software:
- **Python 3.9+**
- **pyserial**: `pip install pyserial`
- **libcamera** (para `rpicam-still`)
- **Raspbian GNU/Linux 12** (Bookworm)

---

## 🔌 Conexiones UART

### Configuración Básica (Solo Datos):
```
Servidor (camaraN1)        Cliente (raspberrypi)
Pin 8  (GPIO14/TXD) ──────→ Pin 10 (GPIO15/RXD)
Pin 10 (GPIO15/RXD) ←────── Pin 8  (GPIO14/TXD)
Pin 6  (GND)        ←────→ Pin 6  (GND)
```

### Configuración Completa (con RTS/CTS):
```
Servidor                   Cliente
Pin 11 (GPIO17/RTS) ──────→ Pin 36 (GPIO16/CTS)
Pin 36 (GPIO16/CTS) ←────── Pin 11 (GPIO17/RTS)
+ conexiones básicas arriba
```

---

## 📁 Estructura del Proyecto

```
sistema-camara-uart/
├── client/
│   └── uart_client_v5.py          # Cliente con protocolo ACK
├── server/
│   ├── APIs/
│   │   ├── photo_api.py            # API de captura (cámara + fallback)
│   │   ├── transport_api.py        # Transporte estándar
│   │   └── transport_api_ack.py    # Transporte con ACK
│   └── uart_server_v5.py           # Servidor con ACK
├── config/
│   ├── config.md                   # Configuración UART
│   ├── uart_config.sh              # Script de configuración
│   └── server_imagen_init.sh       # Servidor de imágenes HTTP
├── docs/
│   ├── conexiones.md               # Esquemas de conexión
│   ├── ejemplos_uso.md             # Ejemplos prácticos
│   └── tests_preliminares.md       # Guía de testing
├── test/
│   ├── test_photo_api.sh           # Test API de captura
│   └── test_imagenes_generadas.sh  # Verificación de imágenes
├── init.sh                         # Script principal de inicio
└── README.md
```

---

## ⚙️ Configuración Previa

### 1. Habilitar UART en Raspberry Pi

Editar `/boot/firmware/config.txt`:
```ini
enable_uart=1
dtoverlay=disable-bt         # Libera UART principal
dtoverlay=uart0,ctsrts       # Habilita RTS/CTS (opcional)
```

### 2. Deshabilitar Console en UART
```bash
sudo systemctl disable --now serial-getty@serial0.service
sudo systemctl disable --now serial-getty@ttyS0.service
```

### 3. Configurar Permisos
```bash
sudo usermod -aG dialout $USER
sudo usermod -aG tty $USER
# Reiniciar sesión para aplicar cambios
```

### 4. Configuración UART Estándar
```bash
# Usando el script incluido
chmod +x config/uart_config.sh
./config/uart_config.sh

# O manualmente:
stty -F /dev/serial0 57600 cs8 -cstopb -parenb crtscts -ixon -ixoff
```

---

## 🚀 Uso del Sistema

### Script Principal `init.sh`

El script `init.sh` es la interfaz principal para ambos modos:

#### Servidor (Raspberry Pi con cámara):
```bash
# Con RTS/CTS (recomendado si está cableado)
./init.sh server --port /dev/serial0 --baud 57600 --rtscts

# Con XON/XOFF (alternativa software)
./init.sh server --port /dev/serial0 --baud 57600 --xonxoff --sleep-ms 2

# Solo fallback (sin cámara)
./init.sh server --port /dev/serial0 --baud 57600 --no-camera \
  --fallback ~/test_fallback.jpg --sleep-ms 1

# Alta velocidad con control de flujo
./init.sh server --port /dev/serial0 --baud 115200 --rtscts \
  --fallback ~/backup.jpg
```

#### Cliente (Raspberry Pi receptor):
```bash
# Configuración estándar
./init.sh client --port /dev/serial0 --baud 57600 --rtscts \
  --resolution HD_READY --resp-timeout 60

# Con salida personalizada
./init.sh client --port /dev/serial0 --baud 57600 --rtscts \
  --resolution FULL_HD --output ~/fotos/captura_$(date +%H%M).jpg

# Para conexiones lentas
./init.sh client --port /dev/serial0 --baud 38400 --xonxoff \
  --resolution THUMBNAIL --resp-timeout 90
```

---

## 📖 Comandos del Protocolo

### Comandos Disponibles:

#### `<FOTO:{size_name:RESOLUTION}>`
Captura y envía inmediatamente:
```bash
echo "<FOTO:{size_name:HD_READY}>" > /dev/serial0
```

#### `<CAPTURAR:{size_name:RESOLUTION}>`
Solo captura (guarda en `/tmp/last.jpg`):
```bash
echo "<CAPTURAR:{size_name:FULL_HD}>" > /dev/serial0
```

#### `<ENVIAR:{path:LAST}>`
Envía última foto capturada:
```bash
echo "<ENVIAR:{path:LAST}>" > /dev/serial0
```

#### `<ENVIAR:{path:/ruta/archivo.jpg}>`
Envía archivo específico:
```bash
echo "<ENVIAR:{path:/home/pi/mi_foto.jpg}>" > /dev/serial0
```

---

## 🔧 Opciones de Configuración

### Variables de Entorno:
```bash
export UART_MODE=server          # server | client
export UART_PORT=/dev/serial0    # Puerto UART
export UART_BAUD=57600          # Velocidad
export UART_RTSCTS=1            # Control de flujo hardware
export UART_XONXOFF=0           # Control de flujo software
export USE_CAMERA=1             # Usar cámara real
export FALLBACK_IMAGE=/path/to/backup.jpg
export SERVER_SLEEP_MS=2        # Pausa entre chunks
export RESP_TIMEOUT=60          # Timeout cliente
```

### Parámetros del Servidor:
- `--sleep-ms N`: Pausa entre chunks (0-10ms, mitiga pérdidas)
- `--no-camera`: Deshabilita cámara, solo fallback
- `--fallback-image PATH`: Imagen de respaldo
- `--rtscts` / `--xonxoff`: Control de flujo

### Parámetros del Cliente:
- `--resolution NAME`: Resolución solicitada
- `--output PATH`: Archivo de salida
- `--resp-timeout N`: Timeout para respuesta del servidor

---

## 🧪 Testing y Verificación

### 1. Test de Captura (Servidor):
```bash
cd server/APIs/
python3 -c "
from photo_api import capture_photo
data = capture_photo('THUMBNAIL', use_camera=True, timeout_s=5)
if data:
    print(f'✅ Cámara OK: {len(data)} bytes')
    with open('/tmp/test_camera.jpg', 'wb') as f: f.write(data)
else:
    print('❌ Cámara falló')
"
```

### 2. Test de Conectividad:
```bash
# En Servidor:
cat /dev/serial0 &

# En Cliente:
echo "TEST_CONEXION" > /dev/serial0
# Debe aparecer "TEST_CONEXION" en el servidor
```

### 3. Test Completo:
```bash
# Terminal 1 (Servidor):
./init.sh server --port /dev/serial0 --baud 57600 --rtscts

# Terminal 2 (Cliente):
./init.sh client --port /dev/serial0 --baud 57600 --rtscts \
  --resolution THUMBNAIL
```

---

## 📊 Protocolo ACK Detallado

### Flujo de Verificación:
1. **Transmisión inicial**: Servidor envía datos completos
2. **Cliente verifica**: Cuenta bytes recibidos vs esperados
3. **ACK_OK**: Si todo está correcto
4. **ACK_MISSING**: Si faltan datos, indica cuántos bytes se recibieron
5. **Retransmisión**: Servidor envía solo los bytes faltantes
6. **Confirmación final**: Cliente confirma recepción completa

### Ejemplo de Logs ACK:
```
[Servidor] 📊 Enviando 45823 bytes con verificación ACK...
[Servidor] 📤 Envío inicial completado, esperando ACK...
[Cliente]  📊 Recepción inicial: 45823/45823 bytes
[Cliente]  📨 Enviando ACK_OK
[Servidor] ✅ ACK_OK - Cliente recibió todo
[Servidor] 🎉 Transmisión verificada exitosamente
```

### En Caso de Pérdida:
```
[Cliente]  📊 Recepción inicial: 45234/45823 bytes
[Cliente]  📨 Enviando ACK_MISSING: faltan 589 bytes
[Servidor] ⚠️ ACK_MISSING - Faltan 589 bytes
[Servidor] 🔄 Retransmitiendo 589 bytes desde offset 45234
[Cliente]  🔄 Leyendo 589 bytes de corrección...
[Cliente]  📨 Enviando ACK_OK
[Servidor] ✅ Corrección exitosa
```

---

## ⚡ Optimización de Rendimiento

### Configuraciones Recomendadas:

#### Conexión Estable (RTS/CTS):
```bash
# Velocidad alta, sin pausas
./init.sh server --baud 115200 --rtscts --sleep-ms 0
./init.sh client --baud 115200 --rtscts
```

#### Conexión Problemática:
```bash
# Velocidad moderada con pausas
./init.sh server --baud 57600 --xonxoff --sleep-ms 3
./init.sh client --baud 57600 --xonxoff --resp-timeout 90
```

#### Conexión Muy Inestable:
```bash
# Velocidad baja, máximas pausas
./init.sh server --baud 38400 --sleep-ms 5
./init.sh client --baud 38400 --resp-timeout 120
```

### Desaceleración Adaptativa:
El sistema automáticamente reduce la velocidad en los últimos KB:
- Últimos 5KB: 5× más lento
- Últimos 2KB: 10× más lento
- Últimos 512B: 20× más lento
- Últimos 256B: 25× más lento

---

## 🛠️ Solución de Problemas

### Error: "Timeout esperando respuesta"
```bash
# Aumentar timeout del cliente
./init.sh client --resp-timeout 90

# Configurar imagen de fallback en servidor
./init.sh server --fallback ~/backup.jpg
```

### Error: "ACK_MISSING persistente"
```bash
# Reducir velocidad y aumentar pausas
./init.sh server --baud 38400 --sleep-ms 5 --xonxoff

# Verificar conexiones físicas (GND, RX↔TX)
```

### Error: "Basura en puerto serial"
```bash
# Deshabilitar getty
sudo systemctl disable --now serial-getty@ttyS0.service

# Limpiar configuración
sudo stty -F /dev/serial0 sane
./config/uart_config.sh
```

### Error: "Permisos denegados"
```bash
# Agregar usuario a grupos necesarios
sudo usermod -aG dialout,tty $USER
# Reiniciar sesión
```

---

## 📈 Monitoreo y Logs

### Logs del Servidor:
- `✅ UART conectado`
- `🎯 FOTO HD_READY` - Comando recibido
- `📊 Enviando X bytes` - Inicio transmisión
- `🐌 Desaceleración` - Últimos KB
- `✅ Envío COMPLETAMENTE VERIFICADO`

### Logs del Cliente:
- `📤 Enviando comando`
- `✅ Respuesta recibida: OK|45823`
- `📊 Progreso: 30000/45823 bytes (65%)`
- `📨 Enviando ACK_OK`
- `✅ PROCESO COMPLETO EXITOSO`

---

## 🔮 Funcionalidades Avanzadas

### Servidor HTTP para Imágenes:
```bash
# Iniciar servidor HTTP en puerto 5000
cd ~/camara-uart/fotos/
python3 -m http.server 5000
# Acceder: http://IP_RASPBERRY:5000
```

### Automatización con systemd:
```bash
# Crear servicio para auto-inicio
sudo tee /etc/systemd/system/uart-camera.service << EOF
[Unit]
Description=UART Camera Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/camara-uart
ExecStart=/home/pi/camara-uart/init.sh server --rtscts
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable uart-camera.service
sudo systemctl start uart-camera.service
```

---

## 📄 Licencia y Créditos

**Licencia**: MIT

**Desarrollado** con enfoque en robustez, verificación de integridad, y recuperación automática de errores. El sistema está optimizado para transmisiones confiables en entornos con posibles interferencias o limitaciones de hardware.

---

## 🤝 Contribuciones

Para reportar problemas, sugerir mejoras o contribuir:
1. Crear issue describiendo el problema/mejora
2. Incluir logs relevantes
3. Especificar configuración de hardware
4. Proporcionar pasos para reproducir

---

## 📚 Documentación Adicional

- **docs/conexiones.md**: Esquemas detallados de conexión
- **docs/ejemplos_uso.md**: Casos de uso específicos
- **config/config.md**: Configuración avanzada UART
- **test/**: Scripts de testing y verificación
