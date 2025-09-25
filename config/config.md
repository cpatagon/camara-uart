# ✅ Configuración previa para usar UART en Raspberry Pi

## 1. Habilitar UART en el firmware

Editar `/boot/firmware/config.txt` (o `/boot/config.txt` en distros más viejas) y agregar:

```ini
enable_uart=1
dtoverlay=disable-bt         # libera el UART PL011 (ttyAMA0) deshabilitando Bluetooth
dtoverlay=uart0,ctsrts       # opcional, activa RTS/CTS en GPIO17/16
```

👉 Reiniciar después:

```bash
sudo reboot
```

---

## 2. Deshabilitar el login por UART

Para evitar que el sistema use el puerto como consola:

```bash
sudo systemctl disable --now serial-getty@serial0.service
sudo systemctl disable --now serial-getty@ttyS0.service
```

---

## 3. Revisar alias del puerto

Confirmar a qué UART apunta `/dev/serial0`:

```bash
ls -l /dev/serial0
```

Debería apuntar a **`ttyAMA0`** si está configurado con `dtoverlay=disable-bt`.

---

## 4. Configurar permisos de usuario

Ver los permisos del dispositivo:

```bash
ls -l /dev/ttyAMA0
```

Normalmente aparece como `root tty` o `root dialout`.
Agrega tu usuario al grupo correspondiente:

```bash
# si pertenece a tty
sudo usermod -aG tty $USER

# si pertenece a dialout
sudo usermod -aG dialout $USER
```

Cerrar sesión o reiniciar para aplicar cambios.

---

## 5. Fijar parámetros de UART

Configurar la velocidad y opciones recomendadas:

```bash
stty -F /dev/serial0 57600 cs8 -cstopb -parenb crtscts -ixon -ixoff
```

Revisar:

```bash
stty -F /dev/serial0 -a | grep -E "speed|cs|cstopb|parenb|crtscts|ixon|ixoff"
```

Salida esperada:

```
speed 57600 baud;
cs8 -cstopb -parenb crtscts
-ixon -ixoff
```

---

## 6. Probar comunicación

### Loopback (en una sola Pi)

Conectar GPIO14 (TX) ↔ GPIO15 (RX):

```bash
cat < /dev/serial0 &
echo "prueba loopback" > /dev/serial0
```

Deberías ver `prueba loopback`.

### Entre dos Pi

* Pi A (escucha):

  ```bash
  cat < /dev/serial0
  ```
* Pi B (envía):

  ```bash
  echo "hola desde PiB" > /dev/serial0
  ```

---

## 7. Opcional: configurar arranque automático

Para que la configuración sea persistente en cada reinicio, agregar al final de `/etc/rc.local` (antes de `exit 0`):

```bash
stty -F /dev/serial0 57600 cs8 -cstopb -parenb crtscts -ixon -ixoff
```

---

👉 Con estos pasos tu sistema queda listo para usar `/dev/serial0` de forma confiable (57600 8N1, sin paridad, con RTS/CTS).

