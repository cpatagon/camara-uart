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
