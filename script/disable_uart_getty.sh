#!/bin/bash
echo "🛑 Eliminando Getty de UART permanentemente..."

# Detener y deshabilitar servicios
sudo systemctl stop serial-getty@ttyAMA0.service 2>/dev/null
sudo systemctl disable serial-getty@ttyAMA0.service 2>/dev/null
sudo systemctl mask serial-getty@ttyAMA0.service 2>/dev/null

# Backup y editar cmdline.txt
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.backup.$(date +%Y%m%d)
sudo sed -i 's/console=serial0,[0-9]*//g' /boot/firmware/cmdline.txt
sudo sed -i 's/console=ttyAMA0,[0-9]*//g' /boot/firmware/cmdline.txt

# Verificar config.txt
if ! grep -q "^enable_uart=1" /boot/firmware/config.txt; then
    echo "enable_uart=1" | sudo tee -a /boot/firmware/config.txt
fi
if ! grep -q "^dtoverlay=disable-bt" /boot/firmware/config.txt; then
    echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt
fi

# Override systemd generator
sudo mkdir -p /etc/systemd/system/serial-getty@ttyAMA0.service.d
sudo tee /etc/systemd/system/serial-getty@ttyAMA0.service.d/override.conf << EOL
[Unit]
ConditionPathExists=
ExecStart=
ExecStart=/bin/true

[Install]
WantedBy=
EOL

sudo systemctl daemon-reload

echo "✅ Getty eliminado permanentemente"
echo "⚠️  REINICIA la RPi para aplicar todos los cambios"
