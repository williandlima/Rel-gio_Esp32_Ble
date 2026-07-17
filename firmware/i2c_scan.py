# Utilitário de diagnóstico: varre o barramento I2C e lista os endereços
# de dispositivos encontrados. O DS3231 deve aparecer como 0x68.

from machine import I2C, Pin
import config

i2c = I2C(0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL))
devices = i2c.scan()

if not devices:
    print("Nenhum dispositivo I2C encontrado. Confira fiação/alimentação do DS3231.")
else:
    print("Dispositivos encontrados:", [hex(d) for d in devices])
