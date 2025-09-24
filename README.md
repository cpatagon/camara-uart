# Sistema Cámara UART — v5

**Cliente por tamaño exacto + APIs separadas de captura y transporte**

> Proyecto para capturar una foto en una Raspberry Pi y transmitirla por UART a un cliente Python de manera **robusta** y **predecible**, leyendo **exactamente** el tamaño anunciado (sin cortar por marcadores que podrían aparecer en los datos comprimidos).

---

## 🔎 Resumen

* **Protocolo v4.1/v5**: el servidor responde `OK|<size>`, luego envía `0xAA*10` + **tamaño 4B big‑endian** + **JPEG (size bytes)**. Marcadores de fin (`0xBB*10`, `<FIN_TRANSMISION>`) son **opcionales** y se ignoran en el cliente.
* **APIs separadas**:

  * `photo_api.py` → *solo captura* (cámara o fallback).
  * `transport_api.py` → *solo transporte* UART por **tamaño exacto**.
* **Cliente**: espera `OK|size` y luego lee **exactamente** `size` bytes. Soporta **RTS/CTS** o **XON/XOFF** y timeout configurable.

---

## Componentes electrónicos

### servidor: 
 * HW: Raspberry Pi Zero W 
 * CAM: Raspberry Module 3 Wide  
 * SO: Raspbian GNU/Linux 12 (bookworm))
### cliente: 
 * HW: Raspberry Pi 3 Model B 
 * SO: Raspbian GNU/Linux 12 (bookworm))

### Comunicación 

# UART en Raspberry Pi — Pines GPIO

## UART básico (sin RTS/CTS)

| Función UART |  GPIO (BCM) |     Pin físico | Conectar a…            |
| ------------ | ----------: | -------------: | ---------------------- |
| TXD0         | **GPIO 14** |          **8** | **RX** del otro equipo |
| RXD0         | **GPIO 15** |         **10** | **TX** del otro equipo |
| GND          |           — | **6 / 9 / 14** | **GND** común          |

## Con control de flujo por hardware (RTS/CTS habilitado)

| Señal    |  GPIO (BCM) | Pin físico | Conectar a…             |
| -------- | ----------: | ---------: | ----------------------- |
| **RTS0** | **GPIO 17** |     **11** | **CTS** servidor        |
| **CTS0** | **GPIO 16** |     **36** | **RTS** cliente         |

**Notas:**

* Niveles lógicos: **3.3 V** (TTL).
* Cruce de líneas: **TX→RX**, **RX→TX**, y en HW flow **RTS↔CTS**.
* `/dev/ttyS0` y `/dev/serial0` usan estos mismos GPIO por defecto.

* Para habilitar RTS/CTS en Raspberry Pi importante activar  el firmware

  - En /boot/firmware/config.txt (Bookworm) o /boot/config.txt (Bullseye y anteriores), agrega:
   
   ```
	dtoverlay=uart0,ctsrts
    ```
	
 
## 📁 Estructura de carpetas

```
sistema-camara-uart/
├── client/
│   ├── APIs/
│   └── uart_client_v5.py
├── server/
│   ├── APIs/
│   │   ├── photo_api.py
│   │   └── transport_api.py
│   └── uart_server_v5.py
└── init.sh
```

**Notas**

* `uart_server_v5.py` importa `photo_api.py` y `transport_api.py` desde `server/APIs`.
* `init.sh` arranca **servidor** o **cliente** con flags uniformes.

---

## 🧩 Requisitos

* **Python 3.9+**
* **pyserial**: `pip install pyserial`
* Raspberry Pi con stack **libcamera** (para `rpicam-still`).
* Permisos de acceso a `/dev/ttyS0` o `/dev/serial0` (usuario en grupo `dialout`).

```bash
# ejemplo
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install --upgrade pyserial
```

---

## ⚙️ Config UART en Raspberry Pi

1. **Habilitar la interfaz serie** (y deshabilitar login por UART):

   * `sudo raspi-config` → *Interface Options* → *Serial Port* → **Login shell: No**; **Serial interface: Yes**.
2. **Deshabilitar getty** si estuviera activo en el mismo puerto:

   ```bash
   sudo systemctl disable --now serial-getty@ttyS0.service || true
   ```
3. **Puertos** típicos:

   * `/dev/serial0` → *alias estable* al UART principal.
   * `/dev/ttyS0` / `/dev/ttyAMA0` según modelo/config.

---

## 🔐 Protocolo (especificación breve)

* **Comandos (cliente → servidor)**

  * `<>` con JSON minimalista estilo `key:value`:

    * `<FOTO:{size_name:THUMBNAIL}>`  → capturar y **enviar** inmediatamente.
    * `<CAPTURAR:{size_name:THUMBNAIL}>` → solo capturar y guardar (servidor responde con `OK|size`).
    * `<ENVIAR:{path:LAST}>` o `<ENVIAR:{path:/ruta/archivo.jpg}>` → enviar archivo (último o ruta).
* **Respuestas (servidor → cliente)**

  * `OK|<size>\r\n` o `BAD|<reason>\r\n`.
* **Stream de datos (tras `OK|size`)**

  1. `0xAA` × 10 (inicio binario)
  2. **tamaño** (4 bytes **big‑endian**)
  3. **JPEG** (`size` bytes exactos)
  4. *(opcional)* `0xBB` × 10 + `<FIN_TRANSMISION>\r\n` (solo para debug humano)

> El **cliente** debe **leer exactamente** el tamaño y **no** cortar por patrones dentro del flujo.

---

## ▶️ Uso con `init.sh`

### Servidor

```bash
# XON/XOFF + fallback y pausas entre chunks (mitiga pérdidas sin flow control HW)
./init.sh server --port /dev/serial0 --baud 57600 --xonxoff \
  --fallback /home/pi/test.jpg --sleep-ms 2

# Con RTS/CTS (si está cableado)
./init.sh server --port /dev/serial0 --baud 57600 --rtscts --sleep-ms 0
```

### Cliente

```bash
# Espera hasta 60 s por OK|size, XON/XOFF, resolución THUMBNAIL
./init.sh client --port /dev/ttyS0 --baud 57600 --xonxoff \
  --resp-timeout 60 --resolution THUMBNAIL

# Con RTS/CTS (si está cableado)
./init.sh client --port /dev/ttyS0 --baud 57600 --rtscts --resp-timeout 45
```

### Variables de entorno equivalentes

* `UART_MODE=server|client`
* `UART_PORT`, `UART_BAUD`
* `UART_XONXOFF=0|1`, `UART_RTSCTS=0|1`
* `USE_CAMERA=1|0`, `FALLBACK_IMAGE=/ruta/test.jpg`
* `SERVER_SLEEP_MS=0..5` (pausa entre chunks en servidor)
* `RESP_TIMEOUT=seg` (timeout cliente para `OK|size`)

---

## 🧪 Ejemplos útiles

**Solo capturar (sin enviar):**

```bash
# desde cualquier terminal conectada al puerto del servidor
echo "<CAPTURAR:{size_name:THUMBNAIL}>" > /dev/ttyS0
# servidor responde: OK|<size>  (guarda en /tmp/last.jpg)
```

**Solo enviar la última foto:**

```bash
echo "<ENVIAR:{path:LAST}>" > /dev/ttyS0
# servidor responde OK|<size> y transmite por tamaño exacto
```

**Flujo completo en un paso (cliente v5):** usa el comando `FOTO`.

---

## 👍 Buenas prácticas para fiabilidad

* **Flow control preferente**: usa **RTS/CTS** si está cableado (`--rtscts`). Si no, **XON/XOFF** (`--xonxoff`).
* **Sin flow control**: agrega `--sleep-ms 1..3` en el servidor y/o baja baudios (p. ej., 38400).
* **Cliente por tamaño exacto**: inmune a falsos positivos por marcadores dentro del JPEG.
* **Cámara lenta**: limita captura con timeout (8 s) y configura **fallback**.

---

## 🛠️ Troubleshooting

**1) Cliente: “Timeout esperando respuesta”**

* El servidor tardó en capturar: aumenta `--resp-timeout` (cliente) o usa `--fallback` (servidor).
* Revisa con: `rpicam-still -n -t 1 -o /tmp/test.jpg`.

**2) Basura / login en el puerto**

* Deshabilita getty y shell por UART (ver sección UART).
* Confirma que **cliente y servidor** usan **el mismo puerto y baudios**.

**3) Recibo menos bytes de los anunciados**

* Activa **flow control** o agrega `--sleep-ms`.
* Verifica cableado GND común, RX↔TX.
* Baja baudios si hay ruido.

**4) Permisos y puertos**

* Agrega tu usuario a `dialout`: `sudo usermod -aG dialout $USER` y vuelve a iniciar sesión.
* Prefiere `/dev/serial0` (alias estable) en lugar de `/dev/ttyS0`.

**5) JPEG inválido (sin FFD8/FFD9)**

* Pérdida parcial: ajusta flow control / pausa / baudios; verifica que el servidor haya enviado `size` correcto.

---

## 📈 Roadmap (opcional)

* **CRC32/MD5** después de la imagen + verificación en cliente.
* **ACK/NACK** por bloque (retransmisión selectiva).
* **Métricas** (tiempos de captura, throughput, retries) y health‑checks.

---

## 📄 Licencia

MIT (sugerida) — ajusta según tus necesidades.

---

## 👤 Créditos

Diseño y mejoras colaborativas con foco en robustez de protocolo y separación de responsabilidades (captura vs transporte).
