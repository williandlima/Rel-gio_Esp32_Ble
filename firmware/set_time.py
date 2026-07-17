# Ajusta o RTC interno do ESP32 com a data/hora atual.
#
# Atenção: o RTC interno do ESP32 NÃO tem bateria de backup — perde a hora
# sempre que a placa perde energia (desliga, reseta). Este script precisa
# ser rodado de novo toda vez que isso acontecer (futuramente isso será
# feito automaticamente pelo app Android via BLE, characteristic SetDateTime).

from machine import RTC

# ---- EDITE AQUI ----
ANO, MES, DIA = 2026, 7, 17
DIA_DA_SEMANA = 5  # 1=Segunda, 2=Terca, 3=Quarta, 4=Quinta, 5=Sexta, 6=Sabado, 7=Domingo
HORA, MINUTO, SEGUNDO = 13, 30, 0
# ---------------------

rtc = RTC()
rtc.datetime((ANO, MES, DIA, DIA_DA_SEMANA, HORA, MINUTO, SEGUNDO, 0))

print("RTC interno ajustado para:", rtc.datetime())
