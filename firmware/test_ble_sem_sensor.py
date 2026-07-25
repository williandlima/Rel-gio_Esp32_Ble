# Variante temporária do teste BLE (etapas 3+5) SEM o sensor DS18B20 — útil
# para testar Display + RTC interno + BLE + Modo Letreiro quando o sensor
# de temperatura não estiver conectado. A temperatura continua no escopo
# do projeto (ver SPECS.md); este arquivo é só uma conveniência de teste.
#
# Use um app BLE genérico (ex: nRF Connect) ou o app Android pra:
#   - Escrever em SetDateTime: {"epoch": 1752500000}  (epoch Unix, segundos
#     desde 1970) -> ajusta o RTC interno na hora.
#   - Escrever em Marquee: {"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}
#     -> ativa o Modo Letreiro: texto rola nas 4 linhas do display pelo
#     tempo configurado, depois volta sozinho ao Modo Normal.
#   - Ler/escrever em Config: {"temp_unit": "C"}
#   - Ler/assinar notificações em Status: {"mode": "normal"|"marquee", "connected": ...}
#     (sem "temp_c" nesta variante, já que não há sensor conectado)

from machine import RTC
from utime import sleep_ms, ticks_ms, ticks_diff, localtime

from lcd_hd44780 import LCD4Bit
from ble_service import ClockBLEService
import config

print("=== test_ble_sem_sensor.py v3 (modo letreiro) ===")

WEEKDAYS = ("", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")

# Diferença, em segundos, entre a época Unix (1970-01-01) e a época usada
# pelo MicroPython no ESP32 (2000-01-01) — necessária para converter o
# "epoch" recebido do app (Unix) para o formato que o RTC espera.
_UNIX_TO_MPY_EPOCH_OFFSET = 946684800

rtc = RTC()

lcd = LCD4Bit(
    rs_pin=config.LCD_RS,
    e_pin=config.LCD_E,
    d4_pin=config.LCD_D4,
    d5_pin=config.LCD_D5,
    d6_pin=config.LCD_D6,
    d7_pin=config.LCD_D7,
    cols=config.LCD_COLS,
    rows=config.LCD_ROWS,
)

# ---- Estado do Modo Letreiro ----
marquee_active = False
marquee_padded = ""
marquee_scroll_offset = 0
marquee_speed_ms = 300
marquee_duration_ms = 0
marquee_start_ticks = 0


def handle_set_datetime(data):
    unix_epoch = data.get("epoch")
    if unix_epoch is None:
        return
    year, month, day, hour, minute, second, wday0, _yday = localtime(
        unix_epoch - _UNIX_TO_MPY_EPOCH_OFFSET
    )
    weekday = wday0 + 1  # localtime: 0=Segunda -> nosso padrão: 1=Segunda
    rtc.datetime((year, month, day, weekday, hour, minute, second, 0))
    print("SetDateTime recebido, RTC ajustado:", rtc.datetime())


def handle_marquee(data):
    global marquee_active, marquee_padded, marquee_scroll_offset
    global marquee_speed_ms, marquee_duration_ms, marquee_start_ticks

    text = data.get("text", "")
    duration_s = data.get("duration_s", 30)
    speed_ms = data.get("speed_ms", 300)

    # Espaços em branco do tamanho do display no início/fim, pra o texto
    # entrar e sair de cena suavemente em vez de "pular" direto na tela.
    marquee_padded = (" " * config.LCD_COLS) + text + (" " * config.LCD_COLS)
    marquee_scroll_offset = 0
    marquee_speed_ms = max(speed_ms, 50)  # evita valor 0/negativo travar o loop
    marquee_duration_ms = int(duration_s * 1000)
    marquee_start_ticks = ticks_ms()
    marquee_active = True

    ble.set_status({"mode": "marquee", "connected": ble.is_connected()})
    print("Modo Letreiro ativado:", text, duration_s, "s @", speed_ms, "ms")


def handle_config_write(data):
    print("Config recebido:", data)


ble = ClockBLEService(name="Relogio-ESP32")
ble.on_set_datetime = handle_set_datetime
ble.on_marquee = handle_marquee
ble.on_config_write = handle_config_write
ble.set_config({"temp_unit": "C"})

STATUS_REFRESH_MS = 5000
last_status_ticks = ticks_ms()

while True:
    if marquee_active:
        if ticks_diff(ticks_ms(), marquee_start_ticks) >= marquee_duration_ms:
            marquee_active = False
            ble.set_status({"mode": "normal", "connected": ble.is_connected()})
            print("Modo Letreiro expirado, voltando ao Modo Normal")
            continue

        scroll_len = len(marquee_padded)
        window = marquee_padded[marquee_scroll_offset:marquee_scroll_offset + config.LCD_COLS]
        if len(window) < config.LCD_COLS:
            window += marquee_padded[: config.LCD_COLS - len(window)]
        for row in range(config.LCD_ROWS):
            lcd.write_line(window, row)
        marquee_scroll_offset = (marquee_scroll_offset + 1) % scroll_len

        sleep_ms(marquee_speed_ms)
        continue

    # ---- Modo Normal ----
    now = ticks_ms()
    if ticks_diff(now, last_status_ticks) >= STATUS_REFRESH_MS:
        ble.set_status({"mode": "normal", "connected": ble.is_connected()})
        last_status_ticks = now

    year, month, day, weekday, hour, minute, second, _ = rtc.datetime()
    date_str = "{}, {:02d}/{:02d}/{:04d}".format(WEEKDAYS[weekday], day, month, year)
    time_str = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)

    lcd.write_line(date_str, row=0)
    lcd.write_line(time_str, row=1)
    lcd.write_line("Sem sensor de temp.", row=2)
    lcd.write_line("Relogio ESP32 BLE", row=3)

    sleep_ms(1000)
