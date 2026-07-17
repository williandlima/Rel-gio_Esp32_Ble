# Script de uso único: grava a hora atual no RTC DS3231.
# Edite os valores abaixo com a data/hora atual e rode uma vez (F5).
# Depois disso o DS3231 mantém a hora sozinho (bateria própria) — não
# precisa rodar este script de novo, a não ser para reajustar o horário.

from machine import I2C, Pin
from rtc_ds3231 import DS3231
import config

# ---- EDITE AQUI ----
ANO = 2026
MES = 7
DIA = 17
DIA_DA_SEMANA = 5  # 1=Segunda, 2=Terca, 3=Quarta, 4=Quinta, 5=Sexta, 6=Sabado, 7=Domingo
HORA = 14
MINUTO = 30
SEGUNDO = 0
# ---------------------

i2c = I2C(0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL))
rtc = DS3231(i2c)
rtc.set_datetime(ANO, MES, DIA, DIA_DA_SEMANA, HORA, MINUTO, SEGUNDO)

print("RTC ajustado para:", rtc.get_datetime())
