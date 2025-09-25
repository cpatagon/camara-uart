#!/usr/bin/env bash
set -euo pipefail





# ---------------- Config por defecto (overrides con flags o env) ----------------
MODE="${UART_MODE:-}"                # server|client (o vacío y se exige por CLI)
PORT="${UART_PORT:-/dev/serial0}"      # en server usualmente /dev/serial0
BAUD="${UART_BAUD:-57600}"
USE_CAMERA="${USE_CAMERA:-1}"        # 1 usa cámara, 0 no usa
FALLBACK_IMAGE="${FALLBACK_IMAGE:-}" # ruta a JPG de respaldo
SLEEP_MS="${SERVER_SLEEP_MS:-0}"     # pausa entre chunks en el server
RESP_TIMEOUT="${RESP_TIMEOUT:-60}"   # timeout del cliente para esperar OK|size

# Flow control (exclusivos): si ambos = 0, va sin flow control
XONXOFF="${UART_XONXOFF:-0}"
RTSCTS="${UART_RTSCTS:-1}"

# ---------------- Utilidades ----------------
SAY(){ printf "\033[1;32m[+] %s\033[0m\n" "$*"; }
WARN(){ printf "\033[1;33m[!] %s\033[0m\n" "$*"; }
ERR(){ printf "\033[1;31m[✗] %s\033[0m\n" "$*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
Uso:
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
  --sleep-ms N         (pausa entre chunks; mitiga pérdidas sin flow control)

Opciones cliente:
  --resp-timeout N     (segundos para esperar OK|size; default ${RESP_TIMEOUT})
  --resolution NAME    (THUMBNAIL | LOW_LIGHT | HD_READY | FULL_HD | ULTRA_WIDE)
  --output PATH.jpg    (ruta de salida)

Variables de entorno equivalentes:
  UART_MODE=server|client, UART_PORT, UART_BAUD, UART_XONXOFF=0/1, UART_RTSCTS=0/1
  USE_CAMERA=1/0, FALLBACK_IMAGE=path, SERVER_SLEEP_MS, RESP_TIMEOUT
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

# ---------------- Comandos ----------------
run_server() {
  SAY "Iniciando servidor en ${PORT} @ ${BAUD} (flow: ${FLOW_FLAGS[*]:-none})"
  local no_cam_flag=()
  [[ "${USE_CAMERA}" == "0" ]] && no_cam_flag+=(--no-camera)
  local fb_flag=()
  [[ -n "${FALLBACK_IMAGE}" ]] && fb_flag+=(--fallback-image "${FALLBACK_IMAGE}")

  exec python3 "${SCRIPT_DIR}/server/uart_server_v5.py" \
      "${PORT}" -b "${BAUD}" "${FLOW_FLAGS[@]}" \
      "${no_cam_flag[@]}" "${fb_flag[@]}" \
      --sleep-ms "${SLEEP_MS}"
}

run_client() {
  SAY "Iniciando cliente en ${PORT} @ ${BAUD} (flow: ${FLOW_FLAGS[*]:-none})"
  local res_flag=(-r "${RESOLUTION:-THUMBNAIL}")
  local out_flag=()
  [[ -n "${OUTPUT_PATH:-}" ]] && out_flag+=(--output "${OUTPUT_PATH}")

  # export para que el script pueda leer RESP_TIMEOUT si lo soporta
  export RESP_TIMEOUT

  exec python3 "${SCRIPT_DIR}/client/uart_client_v5.py" \
      "${PORT}" -b "${BAUD}" "${FLOW_FLAGS[@]}" \
      "${res_flag[@]}" "${out_flag[@]}"
}

case "${MODE}" in
  server) run_server ;;
  client) run_client ;;
  *) ERR "Modo inválido: ${MODE}"; usage; exit 1 ;;
esac
