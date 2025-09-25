#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# init.sh — Script unificado para sistema de cámara UART
# Versión unificada con protocolo ACK robusto
# ============================================================================

# ---------------- Config por defecto ----------------
MODE="${UART_MODE:-}"
PORT="${UART_PORT:-/dev/serial0}"
BAUD="${UART_BAUD:-57600}"
USE_CAMERA="${USE_CAMERA:-1}"
FALLBACK_IMAGE="${FALLBACK_IMAGE:-}"
SLEEP_MS="${SERVER_SLEEP_MS:-0}"
RESP_TIMEOUT="${RESP_TIMEOUT:-60}"

# Protocol ACK (habilitado por defecto)
ENABLE_ACK="${ENABLE_ACK:-1}"
MAX_RETRIES="${MAX_RETRIES:-2}"

# Flow control
XONXOFF="${UART_XONXOFF:-0}"
RTSCTS="${UART_RTSCTS:-1}"

# ---------------- Utilidades ----------------
SAY(){ printf "\033[1;32m[+] %s\033[0m\n" "$*"; }
WARN(){ printf "\033[1;33m[!] %s\033[0m\n" "$*"; }
ERR(){ printf "\033[1;31m[✗] %s\033[0m\n" "$*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
Sistema de Cámara UART - Versión Unificada con Protocolo ACK

Uso:
  $(basename "$0") server [opciones]
  $(basename "$0") client [opciones]

Opciones comunes:
  --port PATH          Puerto serie (default: ${PORT})
  --baud N             Velocidad (default: ${BAUD})
  --xonxoff            Habilitar XON/XOFF
  --rtscts             Habilitar RTS/CTS (default: habilitado)

Opciones servidor:
  --no-camera          Usar solo imagen fallback
  --fallback PATH.jpg  Imagen de respaldo
  --sleep-ms N         Pausa entre chunks (default: ${SLEEP_MS})

Opciones cliente:
  --resp-timeout N     Timeout respuesta servidor (default: ${RESP_TIMEOUT}s)
  --resolution NAME    Resolución: THUMBNAIL|LOW_LIGHT|HD_READY|FULL_HD|ULTRA_WIDE
  --output PATH.jpg    Archivo de salida
  --no-ack            Deshabilitar protocolo ACK (no recomendado)
  --max-retries N     Máximo reintentos (default: ${MAX_RETRIES})

Ejemplos:
  # Servidor con RTS/CTS:
  $(basename "$0") server --port /dev/serial0 --baud 57600 --rtscts

  # Cliente con resolución Full HD:
  $(basename "$0") client --resolution FULL_HD --output foto_hd.jpg

Variables de entorno:
  UART_MODE, UART_PORT, UART_BAUD, UART_RTSCTS, UART_XONXOFF
  USE_CAMERA, FALLBACK_IMAGE, SERVER_SLEEP_MS, RESP_TIMEOUT
  ENABLE_ACK, MAX_RETRIES
EOF
}

# ---------------- Parseo de argumentos ----------------
if [[ "${1:-}" == "server" || "${1:-}" == "client" ]]; then
  MODE="$1"; shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)        PORT="${2:?}"; shift 2 ;;
    --baud)        BAUD="${2:?}"; shift 2 ;;
    --xonxoff)     XONXOFF=1; RTSCTS=0; shift ;;
    --rtscts)      RTSCTS=1; XONXOFF=0; shift ;;
    --no-camera)   USE_CAMERA=0; shift ;;
    --fallback)    FALLBACK_IMAGE="${2:?}"; shift 2 ;;
    --sleep-ms)    SLEEP_MS="${2:?}"; shift 2 ;;
    --resp-timeout)RESP_TIMEOUT="${2:?}"; shift 2 ;;
    --resolution)  RESOLUTION="${2:?}"; shift 2 ;;
    --output)      OUTPUT_PATH="${2:?}"; shift 2 ;;
    --no-ack)      ENABLE_ACK=0; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) ERR "Flag desconocida: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "${MODE}" ]]; then
  ERR "Debes indicar modo: server o client"
  usage; exit 1
fi

# Validar flow control
if [[ "${XONXOFF}" == "1" && "${RTSCTS}" == "1" ]]; then
  ERR "No uses --xonxoff y --rtscts juntos"; exit 1
fi

FLOW_FLAGS=()
[[ "${XONXOFF}" == "1" ]] && FLOW_FLAGS+=(--xonxoff)
[[ "${RTSCTS}" == "1" ]] && FLOW_FLAGS+=(--rtscts)

# ---------------- Verificación de archivos ----------------
check_files() {
  local missing_files=()
  
  if [[ "${MODE}" == "server" ]]; then
    [[ ! -f "${SCRIPT_DIR}/server/APIs/transport_api.py" ]] && missing_files+=("server/APIs/transport_api.py")
    [[ ! -f "${SCRIPT_DIR}/server/APIs/photo_api.py" ]] && missing_files+=("server/APIs/photo_api.py")
    [[ ! -f "${SCRIPT_DIR}/server/uart_server_v5.py" ]] && missing_files+=("server/uart_server_v5.py")
  elif [[ "${MODE}" == "client" ]]; then
    [[ ! -f "${SCRIPT_DIR}/client/uart_client_v5.py" ]] && missing_files+=("client/uart_client_v5.py")
  fi
  
  if [[ ${#missing_files[@]} -gt 0 ]]; then
    ERR "❌ Faltan archivos necesarios:"
    for file in "${missing_files[@]}"; do
      ERR "   • ${file}"
    done
    exit 1
  fi
}

# ---------------- Comandos ----------------
run_server() {
  SAY "🚀 Iniciando SERVIDOR UART con protocolo ACK"
  SAY "Puerto: ${PORT} @ ${BAUD} bauds"
  SAY "Flow control: ${FLOW_FLAGS[*]:-ninguno}"
  SAY "Protocolo ACK: $([ "${ENABLE_ACK}" == "1" ] && echo "✅ HABILITADO" || echo "⚠️ deshabilitado")"
  
  local no_cam_flag=()
  [[ "${USE_CAMERA}" == "0" ]] && no_cam_flag+=(--no-camera)
  local fb_flag=()
  [[ -n "${FALLBACK_IMAGE}" ]] && fb_flag+=(--fallback-image "${FALLBACK_IMAGE}")

  # Exportar variables para el servidor
  export ENABLE_ACK MAX_RETRIES

  exec python3 "${SCRIPT_DIR}/server/uart_server_v5.py" \
      "${PORT}" -b "${BAUD}" "${FLOW_FLAGS[@]}" \
      "${no_cam_flag[@]}" "${fb_flag[@]}" \
      --sleep-ms "${SLEEP_MS}"
}

run_client() {
  SAY "🚀 Iniciando CLIENTE UART con protocolo ACK"
  SAY "Puerto: ${PORT} @ ${BAUD} bauds"  
  SAY "Flow control: ${FLOW_FLAGS[*]:-ninguno}"
  SAY "Protocolo ACK: $([ "${ENABLE_ACK}" == "1" ] && echo "✅ HABILITADO" || echo "⚠️ deshabilitado")"
  SAY "Timeout respuesta: ${RESP_TIMEOUT}s"
  
  local res_flag=(-r "${RESOLUTION:-THUMBNAIL}")
  local out_flag=()
  [[ -n "${OUTPUT_PATH:-}" ]] && out_flag+=(--output "${OUTPUT_PATH}")
  
  local ack_flag=()
  [[ "${ENABLE_ACK}" == "0" ]] && ack_flag+=(--no-ack)

  # Exportar variables para el cliente
  export ENABLE_ACK MAX_RETRIES RESP_TIMEOUT

  exec python3 "${SCRIPT_DIR}/client/uart_client_v5.py" \
      "${PORT}" -b "${BAUD}" "${FLOW_FLAGS[@]}" \
      "${res_flag[@]}" "${out_flag[@]}" "${ack_flag[@]}" 
}

# ---------------- Main ----------------
check_files

case "${MODE}" in
  server) run_server ;;
  client) run_client ;;
  *) ERR "Modo inválido: ${MODE}"; usage; exit 1 ;;
esac
