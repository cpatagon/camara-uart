# Ejemplos de Uso - Sistema Cámara UART v5

**Casos de uso específicos con protocolo ACK y configuraciones optimizadas**

---

## 🏗️ Configuraciones Base por Escenario

### 🏃‍♂️ **Escenario 1: Desarrollo y Testing Rápido**
*Para pruebas frecuentes y desarrollo*

```bash
# SERVIDOR - Modo desarrollo con fallback
./init.sh server --port /dev/serial0 --baud 115200 --rtscts \
  --fallback ~/desarrollo/test_imagen.jpg --sleep-ms 0

# CLIENTE - Capturas rápidas en carpeta de desarrollo  
./init.sh client --port /dev/serial0 --baud 115200 --rtscts \
  --resolution THUMBNAIL --resp-timeout 30 \
  --output ~/desarrollo/prueba_$(date +%H%M%S).jpg
```

**Características:**
- ✅ Resolución baja para velocidad máxima
- ✅ Timeout corto para iteración rápida
- ✅ Imagen de fallback para casos sin cámara
- ✅ Nombres únicos con timestamp

---

### 📊 **Escenario 2: Monitoreo de Calidad (Producción)**
*Para sistemas en producción con máxima confiabilidad*

```bash
# SERVIDOR - Configuración robusta con logging detallado
./init.sh server --port /dev/serial0 --baud 57600 --rtscts \
  --fallback ~/backup/camara_offline.jpg --sleep-ms 1 2>&1 | \
  tee -a ~/logs/servidor_$(date +%Y%m%d).log

# CLIENTE - Captura de alta calidad con validación
./init.sh client --port /dev/serial0 --baud 57600 --rtscts \
  --resolution HD_READY --resp-timeout 90 \
  --output ~/capturas/calidad/img_$(date +%Y%m%d_%H%M%S).jpg 2>&1 | \
  tee -a ~/logs/cliente_$(date +%Y%m%d).log
```

**Características:**
- ✅ Velocidad moderada para estabilidad
- ✅ Logging completo en archivos
- ✅ Timeout generoso para condiciones adversas
- ✅ Resolución balanceada (calidad/velocidad)

---

### 🔬 **Escenario 3: Análisis Científico/Técnico**
*Para aplicaciones que requieren máxima calidad de imagen*

```bash
# SERVIDOR - Máxima calidad con tiempo suficiente
./init.sh server --port /dev/serial0 --baud 38400 --xonxoff \
  --fallback ~/referencias/patron_calibracion.jpg --sleep-ms 5

# CLIENTE - Ultra alta resolución con paciencia
./init.sh client --port /dev/serial0 --baud 38400 --xonxoff \
  --resolution ULTRA_WIDE --resp-timeout 300 \
  --output ~/analisis/muestra_$(date +%Y%m%d_%H%M%S)_4K.jpg
```

**Características:**
- ✅ Máxima resolución (4056×3040)
- ✅ Velocidad reducida para estabilidad
- ✅ Timeout muy largo (5 minutos)
- ✅ XON/XOFF para compatibilidad amplia

---

## 🌐 **Casos de Uso Específicos**

### 📷 **Caso A: Cámara de Seguridad Remota**

**Configuración Automática:**
```bash
#!/bin/bash
# script: camara_seguridad.sh

# Variables de configuración
INTERVALO=300  # 5 minutos entre capturas
RESOLUCION="FULL_HD"
CARPETA_DESTINO="~/seguridad/$(date +%Y%m%d)"

# Crear carpeta si no existe
mkdir -p "$CARPETA_DESTINO"

# Función de captura
capturar_seguridad() {
    local timestamp=$(date +%H%M%S)
    local archivo="${CARPETA_DESTINO}/seg_${timestamp}.jpg"
    
    echo "[$(date)] Iniciando captura de seguridad..."
    
    timeout 120 ./init.sh client --port /dev/serial0 --baud 57600 --rtscts \
        --resolution "$RESOLUCION" --resp-timeout 90 --output "$archivo"
    
    if [[ $? -eq 0 && -f "$archivo" ]]; then
        local tamano=$(du -h "$archivo" | cut -f1)
        echo "[$(date)] ✅ Captura exitosa: $archivo ($tamano)"
        
        # Verificar integridad JPEG
        if file "$archivo" | grep -q "JPEG"; then
            echo "[$(date)] ✅ Archivo JPEG válido"
        else
            echo "[$(date)] ⚠️ Posible corrupción en $archivo"
        fi
    else
        echo "[$(date)] ❌ Captura falló"
    fi
}

# Ejecutar servidor en background
./init.sh server --port /dev/serial0 --baud 57600 --rtscts \
    --fallback ~/seguridad/backup/no_signal.jpg &
SERVER_PID=$!

echo "Servidor iniciado (PID: $SERVER_PID)"
sleep 5

# Loop de captura
while true; do
    capturar_seguridad
    echo "[$(date)] Esperando $INTERVALO segundos..."
    sleep $INTERVALO
done
```

---

### 🏭 **Caso B: Control de Calidad Industrial**

**Sistema de Inspección:**
```bash
#!/bin/bash
# script: inspeccion_calidad.sh

LOTE_ACTUAL=""
CONTADOR=0
CARPETA_BASE="~/inspeccion"

# Función para nueva inspección
nueva_inspeccion() {
    read -p "Ingrese número de lote: " LOTE_ACTUAL
    CONTADOR=0
    
    CARPETA_LOTE="${CARPETA_BASE}/lote_${LOTE_ACTUAL}"
    mkdir -p "$CARPETA_LOTE"
    
    echo "=== NUEVA INSPECCIÓN LOTE $LOTE_ACTUAL ==="
    echo "Carpeta: $CARPETA_LOTE"
}

# Función de captura individual
capturar_pieza() {
    ((CONTADOR++))
    local archivo="${CARPETA_LOTE}/pieza_${CONTADOR}_$(date +%H%M%S).jpg"
    
    echo "--- Pieza #$CONTADOR ---"
    echo "Preparar pieza y presionar ENTER..."
    read
    
    echo "Capturando pieza #$CONTADOR..."
    
    # Captura de alta calidad con verificación
    if ./init.sh client --port /dev/serial0 --baud 57600 --rtscts \
        --resolution FULL_HD --resp-timeout 60 --output "$archivo"; then
        
        echo "✅ Pieza #$CONTADOR capturada: $(basename $archivo)"
        
        # Mostrar estadísticas
        local tamano=$(stat -c%s "$archivo")
        echo "📊 Tamaño: $((tamano / 1024)) KB"
        
        # Opción de visualizar (si hay display)
        if command -v feh >/dev/null 2>&1; then
            read -p "¿Ver imagen? (y/N): " ver
            [[ "$ver" =~ ^[Yy]$ ]] && feh "$archivo" &
        fi
        
    else
        echo "❌ Error capturando pieza #$CONTADOR"
        ((CONTADOR--))  # Revertir contador
    fi
}

# Servidor para inspección industrial
./init.sh server --port /dev/serial0 --baud 57600 --rtscts \
    --fallback ~/inspeccion/referencias/patron_defecto.jpg &

sleep 3

# Menu principal
while true; do
    echo
    echo "=== SISTEMA INSPECCIÓN CALIDAD ==="
    echo "Lote actual: ${LOTE_ACTUAL:-"(ninguno)"}"
    echo "Piezas capturadas: $CONTADOR"
    echo
    echo "1) Nueva inspección"
    echo "2) Capturar pieza"
    echo "3) Finalizar lote"
    echo "4) Salir"
    echo
    read -p "Seleccione opción: " opcion
    
    case $opcion in
        1) nueva_inspeccion ;;
        2) [[ -n "$LOTE_ACTUAL" ]] && capturar_pieza || echo "⚠️ Debe iniciar nueva inspección" ;;
        3) echo "Lote $LOTE_ACTUAL finalizado con $CONTADOR piezas"; LOTE_ACTUAL=""; CONTADOR=0 ;;
        4) echo "Finalizando..."; pkill -f uart_server_v5.py; exit 0 ;;
        *) echo "Opción inválida" ;;
    esac
done
```

---

### 🌦️ **Caso C: Monitoreo Meteorológico**

**Captura Programada con Condiciones:**
```bash
#!/bin/bash
# script: meteocam.sh

CARPETA_METEO="~/meteorologia/$(date +%Y%m%d)"
mkdir -p "$CARPETA_METEO"

# Función para determinar configuración según condiciones
determinar_config() {
    local hora=$(date +%H)
    local minuto=$(date +%M)
    
    # Configuración según hora del día
    if [[ $hora -ge 6 && $hora -le 18 ]]; then
        # Día: captura normal
        echo "HD_READY 57600 60"
    else
        # Noche: captura lenta y cuidadosa
        echo "FULL_HD 38400 120"
    fi
}

# Función de captura meteorológica
captura_meteoro() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local config=($(determinar_config))
    local resolucion=${config[0]}
    local baudrate=${config[1]}
    local timeout=${config[2]}
    
    local archivo="${CARPETA_METEO}/meteo_${timestamp}.jpg"
    local log_file="${CARPETA_METEO}/meteo_${timestamp}.log"
    
    echo "=== CAPTURA METEOROLÓGICA ===" | tee "$log_file"
    echo "Fecha: $(date)" | tee -a "$log_file"
    echo "Resolución: $resolucion" | tee -a "$log_file"
    echo "Velocidad: $baudrate bps" | tee -a "$log_file"
    echo "Timeout: $timeout seg" | tee -a "$log_file"
    
    # Captura con configuración adaptativa
    if timeout $((timeout + 30)) ./init.sh client --port /dev/serial0 \
        --baud "$baudrate" --rtscts --resolution "$resolucion" \
        --resp-timeout "$timeout" --output "$archivo" 2>&1 | tee -a "$log_file"; then
        
        echo "✅ Captura exitosa" | tee -a "$log_file"
        
        # Generar metadatos
        {
            echo "Archivo: $(basename $archivo)"
            echo "Tamaño: $(stat -c%s "$archivo") bytes"
            echo "Resolución configurada: $resolucion"
            file "$archivo"
            
            # Información del sistema
            echo "Temperatura CPU: $(vcgencmd measure_temp)"
            echo "Uso memoria: $(free -h | grep Mem)"
        } >> "${archivo%.jpg}_metadata.txt"
        
    else
        echo "❌ Captura falló" | tee -a "$log_file"
    fi
}

# Servidor meteorológico
./init.sh server --port /dev/serial0 --baud 57600 --rtscts \
    --fallback ~/meteorologia/referencias/cielo_nublado.jpg &

sleep 3

# Programación de capturas
echo "=== SISTEMA METEOROLÓGICO INICIADO ==="
echo "Captura cada 15 minutos"

while true; do
    captura_meteoro
    
    # Esperar hasta próximo intervalo de 15 minutos
    local minutos_actuales=$(date +%M)
    local minutos_hasta_proximo=$(( (15 - minutos_actuales % 15) % 15 ))
    [[ $minutos_hasta_proximo -eq 0 ]] && minutos_hasta_proximo=15
    
    echo "⏰ Próxima captura en $minutos_hasta_proximo minutos"
    sleep $((minutos_hasta_proximo * 60))
done
```

---

### 🔧 **Caso D: Testing y Diagnóstico**

**Suite de Pruebas Automatizadas:**
```bash
#!/bin/bash
# script: test_sistema_completo.sh

CARPETA_TESTS="~/tests/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$CARPETA_TESTS"

echo "=== SUITE DE PRUEBAS SISTEMA UART v5 ==="
echo "Carpeta de resultados: $CARPETA_TESTS"

# Test 1: Conectividad básica
test_conectividad() {
    echo
    echo "🔍 TEST 1: CONECTIVIDAD BÁSICA"
    echo "Probando comunicación serial..."
    
    # Iniciar servidor en background
    timeout 30 ./init.sh server --port /dev/serial0 --baud 57600 \
        --no-camera --fallback ~/tests/patron_test.jpg &
    local server_pid=$!
    
    sleep 5
    
    # Test simple de eco
    echo "TEST_PING" > /dev/serial0 &
    sleep 2
    
    if ps -p $server_pid > /dev/null; then
        echo "✅ Servidor respondiendo"
        kill $server_pid 2>/dev/null
    else
        echo "❌ Servidor no responde"
    fi
}

# Test 2: Velocidades múltiples
test_velocidades() {
    echo
    echo "🔍 TEST 2: VELOCIDADES MÚLTIPLES"
    
    local velocidades=(9600 19200 38400 57600 115200)
    
    for baud in "${velocidades[@]}"; do
        echo "Probando $baud bps..."
        
        timeout 60 ./init.sh server --port /dev/serial0 --baud "$baud" \
            --no-camera --fallback ~/tests/patron_test.jpg &
        local server_pid=$!
        
        sleep 3
        
        local archivo_test="${CARPETA_TESTS}/test_${baud}bps.jpg"
        if timeout 45 ./init.sh client --port /dev/serial0 --baud "$baud" \
            --resolution THUMBNAIL --resp-timeout 30 --output "$archivo_test"; then
            echo "✅ $baud bps: OK ($(stat -c%s "$archivo_test") bytes)"
        else
            echo "❌ $baud bps: FALLO"
        fi
        
        kill $server_pid 2>/dev/null
        sleep 2
    done
}

# Test 3: Resoluciones múltiples
test_resoluciones() {
    echo
    echo "🔍 TEST 3: RESOLUCIONES MÚLTIPLES"
    
    local resoluciones=(THUMBNAIL LOW_LIGHT HD_READY FULL_HD)
    
    # Servidor con cámara real
    ./init.sh server --port /dev/serial0 --baud 57600 --rtscts &
    local server_pid=$!
    sleep 5
    
    for res in "${resoluciones[@]}"; do
        echo "Probando resolución $res..."
        
        local archivo_test="${CARPETA_TESTS}/test_${res}.jpg"
        local inicio=$(date +%s)
        
        if timeout 120 ./init.sh client --port /dev/serial0 --baud 57600 --rtscts \
            --resolution "$res" --resp-timeout 90 --output "$archivo_test"; then
            
            local fin=$(date +%s)
            local duracion=$((fin - inicio))
            local tamano=$(stat -c%s "$archivo_test")
            
            echo "✅ $res: OK - ${tamano} bytes en ${duracion}s"
        else
            echo "❌ $res: FALLO"
        fi
    done
    
    kill $server_pid 2>/dev/null
}

# Test 4: Protocolo ACK bajo estrés
test_protocolo_ack() {
    echo
    echo "🔍 TEST 4: PROTOCOLO ACK (ESTRÉS)"
    
    # Simulación de conexión problemática
    ./init.sh server --port /dev/serial0 --baud 38400 --xonxoff --sleep-ms 3 &
    local server_pid=$!
    sleep 5
    
    local intentos=5
    local exitosos=0
    
    for i in $(seq 1 $intentos); do
        echo "Intento $i/$intentos con condiciones adversas..."
        
        local archivo_test="${CARPETA_TESTS}/test_ack_${i}.jpg"
        
        if timeout 180 ./init.sh client --port /dev/serial0 --baud 38400 --xonxoff \
            --resolution HD_READY --resp-timeout 150 --output "$archivo_test"; then
            echo "✅ Intento $i: EXITOSO"
            ((exitosos++))
        else
            echo "❌ Intento $i: FALLO"
        fi
    done
    
    echo "📊 Protocolo ACK: $exitosos/$intentos exitosos ($(( exitosos * 100 / intentos ))%)"
    
    kill $server_pid 2>/dev/null
}

# Test 5: Estadísticas de rendimiento
generar_estadisticas() {
    echo
    echo "🔍 GENERANDO ESTADÍSTICAS"
    
    local archivo_stats="${CARPETA_TESTS}/estadisticas.txt"
    
    {
        echo "=== ESTADÍSTICAS DE PRUEBAS ==="
        echo "Fecha: $(date)"
        echo "Sistema: $(uname -a)"
        echo "Python: $(python3 --version)"
        echo
        
        echo "=== ARCHIVOS GENERADOS ==="
        ls -lh "$CARPETA_TESTS"/*.jpg 2>/dev/null || echo "No hay archivos de imagen"
        echo
        
        echo "=== VERIFICACIÓN JPEG ==="
        for jpg in "$CARPETA_TESTS"/*.jpg; do
            [[ -f "$jpg" ]] || continue
            echo "$(basename "$jpg"): $(file "$jpg" | cut -d: -f2-)"
        done
        
        echo
        echo "=== INFORMACIÓN DEL SISTEMA ==="
        echo "Temperatura CPU: $(vcgencmd measure_temp 2>/dev/null || echo 'N/A')"
        echo "Memoria libre: $(free -h | grep Mem | awk '{print $7}')"
        echo "Espacio disco: $(df -h . | tail -1 | awk '{print $4}')"
        
    } > "$archivo_stats"
    
    echo "📊 Estadísticas guardadas en: $archivo_stats"
    cat "$archivo_stats"
}

# Ejecutar todos los tests
echo "Iniciando batería de pruebas..."

test_conectividad
test_velocidades  
test_resoluciones
test_protocolo_ack
generar_estadisticas

echo
echo "🎉 PRUEBAS COMPLETADAS"
echo "📁 Resultados en: $CARPETA_TESTS"
echo "📊 Ver estadísticas: cat $CARPETA_TESTS/estadisticas.txt"
```

---

## ⚙️ **Configuraciones por Variables de Entorno**

### 🚀 **Setup Rápido para Desarrollo:**
```bash
# .env_desarrollo
export UART_MODE=server
export UART_PORT=/dev/serial0  
export UART_BAUD=115200
export UART_RTSCTS=1
export USE_CAMERA=0
export FALLBACK_IMAGE=~/dev/test_pattern.jpg
export SERVER_SLEEP_MS=0

# Uso:
source .env_desarrollo && ./init.sh server
```

### 🏭 **Setup para Producción:**
```bash
# .env_produccion  
export UART_MODE=server
export UART_PORT=/dev/serial0
export UART_BAUD=57600
export UART_RTSCTS=1  
export USE_CAMERA=1
export FALLBACK_IMAGE=~/backup/emergency.jpg
export SERVER_SLEEP_MS=2

# Uso:
source .env_produccion && ./init.sh server
```

### 🔬 **Setup para Laboratorio:**
```bash
# .env_laboratorio
export UART_MODE=client
export UART_PORT=/dev/serial0
export UART_BAUD=38400
export UART_XONXOFF=1
export RESP_TIMEOUT=300

# Uso:
source .env_laboratorio && ./init.sh client --resolution ULTRA_WIDE \
  --output ~/lab/experimento_$(date +%Y%m%d_%H%M).jpg
```

---

## 🔄 **Scripts de Automatización**

### 📅 **Captura Programada (Cron):**
```bash
# Agregar a crontab (crontab -e):

# Cada hora durante el día
0 8-18 * * * /home/pi/camara-uart/scripts/captura_horaria.sh

# Cada 5 minutos durante horario crítico  
*/5 9-17 * * 1-5 /home/pi/camara-uart/scripts/captura_frecuente.sh

# Captura nocturna (una vez)
0 23 * * * /home/pi/camara-uart/scripts/captura_nocturna.sh
```

### 🔄 **Reinicio Automático en Fallos:**
```bash
#!/bin/bash
# script: watchdog_camara.sh

LOCK_FILE="/tmp/camara_uart.lock"
LOG_FILE="~/logs/watchdog_$(date +%Y%m%d).log"

while true; do
    if [[ ! -f "$LOCK_FILE" ]]; then
        echo "[$(date)] Iniciando servidor..." >> "$LOG_FILE"
        
        # Crear lock
        echo $$ > "$LOCK_FILE"
        
        # Iniciar servidor con reinicio automático
        while true; do
            ./init.sh server --port /dev/serial0 --baud 57600 --rtscts \
                --fallback ~/backup/sistema_reiniciado.jpg 2>&1 >> "$LOG_FILE"
            
            echo "[$(date)] Servidor terminó, reiniciando en 10s..." >> "$LOG_FILE"
            sleep 10
        done
    else
        echo "[$(date)] Servidor ya ejecutándose (PID: $(cat $LOCK_FILE))" >> "$LOG_FILE"
    fi
    
    sleep 60
done
```

---

## 📊 **Monitoreo y Métricas**

### 📈 **Dashboard Simple:**
```bash
#!/bin/bash
# script: dashboard.sh

watch -n 5 '
echo "=== DASHBOARD CÁMARA UART v5 ==="
echo "Fecha: $(date)"
echo
echo "=== PROCESOS ==="
pgrep -f uart_server_v5.py >/dev/null && echo "✅ Servidor: ACTIVO" || echo "❌ Servidor: INACTIVO"
pgrep -f uart_client_v5.py >/dev/null && echo "✅ Cliente: ACTIVO" || echo "❌ Cliente: INACTIVO"
echo
echo "=== SISTEMA ==="
echo "CPU Temp: $(vcgencmd measure_temp 2>/dev/null || echo N/A)"
echo "Memoria: $(free -h | grep Mem | awk "{print \$3\"/\"\$2}")"
echo "Disco: $(df -h . | tail -1 | awk "{print \$3\"/\"\$2\" (\"\$5\")"}"
echo
echo "=== CAPTURAS HOY ==="
echo "Total: $(find ~/capturas -name "*.jpg" -newermt "today" 2>/dev/null | wc -l)"
echo "Última: $(ls -t ~/capturas/*.jpg 2>/dev/null | head -1 | xargs stat -c "%y %n" 2>/dev/null || echo "Ninguna")"
echo
echo "=== PUERTO UART ==="
stty -F /dev/serial0 -a 2>/dev/null | head -1 || echo "Puerto no accesible"
echo
echo "Presiona Ctrl+C para salir"
'
```

Este documento proporciona ejemplos prácticos y completos que aprovechan todas las características del sistema v5 con protocolo ACK, desde desarrollo hasta producción, incluyendo casos de uso específicos para diferentes industrias y aplicaciones.
