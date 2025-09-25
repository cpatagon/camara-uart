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
