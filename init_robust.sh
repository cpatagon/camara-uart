#!/usr/bin/env bash
set -euo pipefail

# Versión ROBUSTA del init.sh que usa las APIs mejoradas
# ---------------- Config por defecto (overrides con flags o env) ----------------
MODE="${UART_MODE:-}"                # server|client (o vacío y se exige por CLI)
PORT="${UART_PORT:-/dev/serial0}"      # en server usualmente /dev/serial0
BAUD="${UART_BAUD:-57600}"
USE_CAMERA="${USE_CAMERA:-1}"        # 1 usa cámara, 0 no usa
FALLBACK_IMAGE="${FALLBACK_IMAGE:-}" # ruta a JPG de respaldo
SLEEP_MS="${SERVER_SLEEP_MS:-1}"     # pausa entre chunks (menos crítico con protocolo robusto)
RESP_TIMEOUT="${RESP_TIMEOUT:-60}"   # timeout del cliente para esperar OK|size (más largo)

# Flow control (exclusivos): si ambos = 0, va sin flow control
XONXOFF="${UART_XONXOFF:-0}"
RTSCTS="${UART_RTSCTS:-1}"

# Nuevas opciones robustas
ENABLE_ACK="${ENABLE_ACK:-1}"        # 1 habilita protocolo ACK, 0 lo deshabilita
MAX_RETRIES="${MAX_RETRIES:-2}"      # número máximo de reintentos

# ---------------- Utilidades ----------------
SAY(){ printf "\033[1;32m[+] %s\033[0m\n" "$*"; }
WARN(){ printf "\033[1;33m[!] %s\033[0m\n" "$*"; }
ERR(){ printf "\033[1;31m[✗] %s\033[0m\n" "$*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
🚀 UART ROBUSTO - Uso:
  $(basename "$0") server [opciones]
  $(basename "$0") client [opciones]

Opciones comunes:
  --port PATH          (default: ${PORT})
  --baud N             (default: ${BAUD})
  --xonxoff            (habilita XON/XOFF)
  --rtscts             (habilita RTS/CTS; no usar junto con --xonxoff)

Opciones servidor:
  --no-camera          (no usar cámara, sólo fallback)
  --fallback PATH.jpg  (imagen de respaldo)
  --sleep-ms N         (pausa entre chunks; default ${SLEEP_MS}ms - menos crítico con protocolo robusto)

Opciones cliente:
  --resp-timeout N     (segundos para esperar OK|size; default ${RESP_TIMEOUT})
  --resolution NAME    (THUMBNAIL | LOW_LIGHT | HD_READY | FULL_HD | ULTRA_WIDE)
  --output PATH.jpg    (ruta de salida)
  --no-ack             (deshabilitar protocolo ACK - no recomendado)

🎯 Mejoras robustas:
  • Eliminación de chunks problemáticos de 110ms
  • Protocolo ACK bidireccional con retransmisión
  • Sincronización mejorada servidor-cliente
  • Verificación de integridad JPEG
  • Timeouts extendidos para mayor confiabilidad

Variables de entorno equivalentes:
  UART_MODE=server|client, UART_PORT, UART_BAUD, UART_XONXOFF=0/1, UART_RTSCTS=0/1
  USE_CAMERA=1/0, FALLBACK_IMAGE=path, SERVER_SLEEP_MS, RESP_TIMEOUT
  ENABLE_ACK=1/0, MAX_RETRIES=N
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
    --xonxoff)     XONXOFF=1; shift ;;
    --rtscts)      RTSCTS=1; shift ;;
    --no-camera)   USE_CAMERA=0; shift ;;
    --fallback)    FALLBACK_IMAGE="${2:?}"; shift 2 ;;
    --sleep-ms)    SLEEP_MS="${2:?}"; shift 2 ;;
    --resp-timeout)RESP_TIMEOUT="${2:?}"; shift 2 ;;
    --resolution)  RESOLUTION="${2:?}"; shift 2 ;;
    --output)      OUTPUT_PATH="${2:?}"; shift 2 ;;
    --no-ack)      ENABLE_ACK=0; shift ;;
    --max-retries) MAX_RETRIES="${2:?}"; shift 2 ;;
    -h|--help)     usage; exit 0 ;;
    *) ERR "Flag desconocida: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "${MODE}" ]]; then
  ERR "Debes indicar modo: server o client"
  usage; exit 1
fi

if [[ "${XONXOFF}" == "1" && "${RTSCTS}" == "1" ]]; then
  ERR "No uses --xonxoff y --rtscts juntos"; exit 1
fi

FLOW_FLAGS=()
[[ "${XONXOFF}" == "1" ]] && FLOW_FLAGS+=(--xonxoff)
[[ "${RTSCTS}" == "1" ]] && FLOW_FLAGS+=(--rtscts)

# ---------------- Verificación de archivos robustos ----------------
check_robust_files() {
  local missing_files=()
  
  if [[ "${MODE}" == "server" ]]; then
    if [[ ! -f "${SCRIPT_DIR}/server/APIs/transport_api_robust.py" ]]; then
      missing_files+=("server/APIs/transport_api_robust.py")
    fi
    if [[ ! -f "${SCRIPT_DIR}/uart_server_robust.py" ]]; then
      missing_files+=("uart_server_robust.py")
    fi
  elif [[ "${MODE}" == "client" ]]; then
    if [[ ! -f "${SCRIPT_DIR}/uart_client_robust.py" ]]; then
      missing_files+=("uart_client_robust.py")
    fi
  fi
  
  if [[ ${#missing_files[@]} -gt 0 ]]; then
    ERR "❌ Faltan archivos robustos:"
    for file in "${missing_files[@]}"; do
      ERR "   • ${file}"
    done
    WARN "💡 Crea los archivos robustos antes de continuar."
    WARN "💡 O usa el init.sh original para la versión estándar."
    exit 1
  fi
}

# ---------------- Comandos robustos ----------------
run_server_robust() {
  SAY "🚀 Iniciando SERVIDOR ROBUSTO en ${PORT} @ ${BAUD}"
  SAY "Flow control: ${FLOW_FLAGS[*]:-none}"
  SAY "Protocolo ACK: $([ "${ENABLE_ACK}" == "1" ] && echo "HABILITADO" || echo "deshabilitado")"
  
  local no_cam_flag=()
  [[ "${USE_CAMERA}" == "0" ]] && no_cam_flag+=(--no-camera)
  local fb_flag=()
  [[ -n "${FALLBACK_IMAGE}" ]] && fb_flag+=(--fallback-image "${FALLBACK_IMAGE}")

  # Exportar variables para el servidor
  export ENABLE_ACK MAX_RETRIES

  exec python3 "${SCRIPT_DIR}/uart_server_robust.py" \
      "${PORT}" -b "${BAUD}" "${FLOW_FLAGS[@]}" \
      "${no_cam_flag[@]}" "${fb_flag[@]}" \
      --sleep-ms "${SLEEP_MS}"
}

run_client_robust() {
  SAY "🚀 Iniciando CLIENTE ROBUSTO en ${PORT} @ ${BAUD}"
  SAY "Flow control: ${FLOW_FLAGS[*]:-none}"
  SAY "Protocolo ACK: $([ "${ENABLE_ACK}" == "1" ] && echo "HABILITADO" || echo "deshabilitado")"
  SAY "Timeout respuesta: ${RESP_TIMEOUT}s (extendido para robustez)"
  
  local res_flag=(-r "${RESOLUTION:-THUMBNAIL}")
  local out_flag=()
  [[ -n "${OUTPUT_PATH:-}" ]] && out_flag+=(--output "${OUTPUT_PATH}")
  local ack_flag=()
  [[ "${ENABLE_ACK}" == "0" ]] && ack_flag+=(--no-ack)

  # Exportar variables para el cliente
  export RESP_TIMEOUT ENABLE_ACK

  exec python3 "${SCRIPT_DIR}/uart_client_robust.py" \
      "${PORT}" -b "${BAUD}" "${FLOW_FLAGS[@]}" \
      "${res_flag[@]}" "${out_flag[@]}" "${ack_flag[@]}" \
      --resp-timeout "${RESP_TIMEOUT}"
}

# ---------------- Función principal ----------------
check_robust_files

case "${MODE}" in
  server) run_server_robust ;;
  client) run_client_robust ;;
  *) ERR "Modo inválido: ${MODE}"; usage; exit 1 ;;
esac
