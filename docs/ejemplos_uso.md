# Ejemplos de uso

## Servidor con RTS/CTS
```
 ./init.sh server --port /dev/serial0 --baud 57600 --rtscts --sleep-ms 0
```
## Cliente con RTS/CTS
```
 ./init.sh client --port /dev/serial0 --baud 57600 --rtscts --resp-timeout 45
```
## Cliente con directorio de imagen
```
 sudo ~/camara-uart/init.sh client --port /dev/serial0 --baud 115200  --output ~/camara-uart/fotos/prueba_$(date +%H%M).jpg
```
