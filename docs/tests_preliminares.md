# Tests Corregidos - Siguientes Pasos

## ✅ Lo que sabemos hasta ahora:
- **Cámara**: ✅ Funciona perfectamente (41,263 bytes)
- **Sistema**: ✅ Python y APIs cargan correctamente  
- **Fallback**: ❌ Necesita una imagen de respaldo

## 🔧 Paso 1: Crear imagen de fallback

```bash
# Opción A: Usar la imagen que acabas de capturar
cp /tmp/test_camera.jpg ~/test_fallback.jpg

# Opción B: Descargar una imagen de prueba
wget -O ~/test_fallback.jpg "https://via.placeholder.com/320x240/FF0000/FFFFFF.png?text=FALLBACK"

# Opción C: Tomar una foto ahora para usar como fallback
rpicam-still -n -t 1 --width 320 --height 240 -o ~/test_fallback.jpg
```

## 🧪 Paso 2: Test corregido de photo_api

```bash
cd ~/camara-uart/server/APIs/

# Test corregido (comando completo en una línea):
python3 -c "
from photo_api import capture_photo
import os

print('=== Test photo_api CORREGIDO ===')

# Test con fallback (usando imagen real)
print('Probando fallback...')
data = capture_photo('THUMBNAIL', use_camera=False, fallback_image='/home/pi/test_fallback.jpg')
if data:
    print(f'✅ Fallback OK: {len(data)} bytes')
    with open('/tmp/test_fallback_output.jpg', 'wb') as f:
        f.write(data)
else:
    print('❌ Fallback falló')

# Test con cámara
print('Probando cámara...')
data = capture_photo('THUMBNAIL', use_camera=True, timeout_s=5)
if data:
    print(f'✅ Cámara OK: {len(data)} bytes')
    with open('/tmp/test_camera_output.jpg', 'wb') as f:
        f.write(data)
else:
    print('❌ Cámara falló')

print('=== Test completado ===')
"
```

## 🔍 Paso 3: Verificar imágenes generadas

```bash
# Ver qué archivos se crearon:
ls -la /tmp/test_*.jpg

# Verificar que son JPEGs válidos:
file /tmp/test_*.jpg

# Ver tamaños:
du -h /tmp/test_*.jpg

# Verificar estructura JPEG (primeros y últimos bytes):
echo "=== Inicio de archivos (debe ser FFD8) ==="
xxd /tmp/test_camera.jpg | head -1
xxd /tmp/test_fallback_output.jpg | head -1 2>/dev/null || echo "No existe"

echo "=== Final de archivos (debe terminar en FFD9) ==="  
xxd /tmp/test_camera.jpg | tail -1
xxd /tmp/test_fallback_output.jpg | tail -1 2>/dev/null || echo "No existe"
```

## 🚀 Paso 4: Test del servidor completo

```bash
cd ~/camara-uart/

# Hacer ejecutable si no lo es:
chmod +x init.sh

# Test servidor con fallback:
echo "=== Iniciando servidor de prueba ==="
./init.sh server --port /dev/serial0 --baud 57600 \
  --no-camera --fallback ~/test_fallback.jpg --sleep-ms 1

# El servidor debe mostrar:
# ✅ UART: /dev/serial0 @ 57600
# 🟢 Esperando comandos...
```

## 🧪 Paso 5: Test manual de comandos

```bash
# Mientras el servidor está ejecutándose, en OTRA terminal:

# Test comando CAPTURAR:
echo "<CAPTURAR:{size_name:THUMBNAIL}>" > /dev/serial0

# Test comando ENVIAR:
echo "<ENVIAR:{path:LAST}>" > /dev/serial0

# Monitorear respuestas del servidor (en otra terminal):
timeout 10 cat /dev/serial0
```

## ✨ Paso 6: Test con cámara real

```bash
# Detener servidor anterior (Ctrl+C)

# Servidor CON cámara:
./init.sh server --port /dev/serial0 --baud 115200 \
  --fallback ~/test_fallback.jpg --sleep-ms 1

# Probar comando FOTO (captura + envío):
echo "<FOTO:{size_name:THUMBNAIL}>" > /dev/serial0
```

## 📋 Resultados esperados:

### ✅ Si todo funciona bien:
```
=== Test photo_api CORREGIDO ===
Probando fallback...
✅ Fallback OK: XXXX bytes
Probando cámara...  
✅ Cámara OK: XXXX bytes
=== Test completado ===
```

### 🔧 Para el servidor:
```
✅ UART: /dev/serial0 @ 57600 (rtscts=False, xonxoff=False)
🟢 Esperando comandos...
🎯 CAPTURAR THUMBNAIL
💾 Imagen guardada en /tmp/last.jpg (XXXX bytes)
```

## 🎯 Próximos pasos después de esto:

1. **Si todo funciona**: Proceder con test cliente-servidor
2. **Si hay errores**: Diagnosticar y corregir
3. **Optimizar configuración**: Baudrate, flow control, etc.
