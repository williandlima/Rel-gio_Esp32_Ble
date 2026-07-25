# Aplicação completa do relógio (ver SPECS.md): Modo Normal (data, hora e
# temperatura) + Modo Letreiro, tudo configurável por BLE.
#
# Este módulo concentra a lógica que antes estava duplicada entre
# test_ble.py e test_ble_sem_sensor.py. Os pontos de entrada (main.py,
# test_ble.py, test_ble_sem_sensor.py) são apenas atalhos para run().
#
# O sensor de temperatura é detectado automaticamente: sem DS18B20 no
# barramento, o relógio sobe normalmente e a linha 3 mostra um aviso —
# não existe mais "versão sem sensor".
#
# Arquivos necessários no ESP32: config.py, lcd_hd44780.py, ble_service.py,
# storage.py, clock_app.py (+ ds18b20_sensor.py, se houver sensor).

from machine import RTC
from utime import sleep_ms, ticks_ms, ticks_add, ticks_diff, localtime, mktime

import config
import lcd_hd44780
import ble_service
import storage
from lcd_hd44780 import LCD4Bit
from ble_service import ClockBLEService

VERSION = "clock_app v1"

_WEEKDAYS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")

# Diferença, em segundos, entre a época Unix (1970-01-01) e a época usada
# pelo MicroPython no ESP32 (2000-01-01).
_UNIX_TO_MPY_EPOCH_OFFSET = 946684800

# Epoch mínimo aceito (2020-01-01): protege o RTC de um payload absurdo.
_MIN_VALID_EPOCH = 1577836800

_LOOP_SLEEP_MS = 20        # granularidade do laço: BLE responde em ~20ms
_TEMP_REFRESH_MS = 5000
_STATUS_REFRESH_MS = 5000
_SENSOR_RESCAN_MS = 30000  # tenta redetectar um sensor ligado depois
_MIN_SPEED_MS = 50
_MAX_DURATION_S = 3600


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sanitize(text):
    """Troca por '?' tudo que o HD44780 não sabe desenhar. O app Android já
    remove acentos antes de enviar; isto é a rede de segurança para quem
    escrever direto por um app BLE genérico (nRF Connect, etc.)."""
    out = []
    for ch in text:
        out.append(ch if 0x20 <= ord(ch) <= 0x7D else "?")
    return "".join(out)


def _weekday_name(year, month, day):
    # Calculado a partir da data, e não do campo weekday devolvido pelo RTC:
    # a porta ESP32 recalcula esse campo por conta própria e a convenção
    # (base 0 ou base 1) varia entre versões do firmware MicroPython.
    try:
        return _WEEKDAYS[localtime(mktime((year, month, day, 0, 0, 0, 0, 0)))[6]]
    except Exception:
        return "---"


class ClockApp:
    def __init__(self):
        print("=== ", VERSION, " ===")

        self._rtc = RTC()
        self._lcd = LCD4Bit(
            rs_pin=config.LCD_RS,
            e_pin=config.LCD_E,
            d4_pin=config.LCD_D4,
            d5_pin=config.LCD_D5,
            d6_pin=config.LCD_D6,
            d7_pin=config.LCD_D7,
            cols=config.LCD_COLS,
            rows=config.LCD_ROWS,
        )

        self._sensor, sensor_version = self._init_sensor()
        print("Modulos carregados:", config.VERSION, "|", lcd_hd44780.VERSION,
              "|", ble_service.VERSION, "|", storage.VERSION, "|", sensor_version)

        self._temp_unit = storage.load_temp_unit()
        self._last_temp_c = None
        self._last_temp_ticks = ticks_ms()
        self._last_scan_ticks = ticks_ms()
        self._last_status_ticks = ticks_ms()
        self._last_second = None

        self._marquee_active = False
        self._marquee_padded = ""
        self._marquee_offset = 0
        self._marquee_speed_ms = 300
        self._marquee_duration_ms = 0
        self._marquee_start = 0
        self._marquee_last_scroll = 0

        self._ble = ClockBLEService(name="Relogio-ESP32")
        self._ble.on_set_datetime = self._handle_set_datetime
        self._ble.on_marquee = self._handle_marquee
        self._ble.on_config_write = self._handle_config_write
        self._ble.set_config({"temp_unit": self._temp_unit})

    def _init_sensor(self):
        try:
            import ds18b20_sensor
            sensor = ds18b20_sensor.DS18B20(config.ONEWIRE_DATA)
        except Exception as e:
            print("Sensor de temperatura indisponivel:", e)
            return None, "sem ds18b20_sensor"
        if not sensor.available:
            print("Nenhum DS18B20 no barramento - relogio segue sem temperatura.")
        return sensor, ds18b20_sensor.VERSION

    # ---- Laço principal ----

    def run(self):
        while True:
            try:
                self._loop_once()
            except Exception as e:
                # Um relógio que fica ligado sozinho não pode morrer por um
                # erro pontual (CRC do 1-Wire, hiccup do BLE, payload torto).
                print("Erro no laco principal:", e)
                sleep_ms(500)

    def _loop_once(self):
        self._ble.tick()
        self._service_temperature()
        if self._marquee_active:
            self._render_marquee()
        else:
            self._render_clock()
        self._service_status()
        sleep_ms(_LOOP_SLEEP_MS)

    # ---- Temperatura (máquina de estados, sem bloquear) ----

    def _service_temperature(self):
        sensor = self._sensor
        if sensor is None:
            return
        now = ticks_ms()

        if sensor.result_ready():
            value = sensor.read_result()
            if value is not None:
                self._last_temp_c = value
            self._last_temp_ticks = now
            return

        if sensor.conversion_pending:
            return

        if not sensor.available:
            if ticks_diff(now, self._last_scan_ticks) >= _SENSOR_RESCAN_MS:
                self._last_scan_ticks = now
                sensor.rescan()
            return

        if ticks_diff(now, self._last_temp_ticks) >= _TEMP_REFRESH_MS:
            sensor.start_conversion()

    def _temp_text(self):
        if self._last_temp_c is None:
            if self._sensor is None or not self._sensor.available:
                return "Sem sensor de temp."
            return "Temp: --"
        if self._temp_unit == "F":
            return "Temp: {:.1f} F".format(self._last_temp_c * 9 / 5 + 32)
        return "Temp: {:.1f} C".format(self._last_temp_c)

    # ---- Renderização ----

    def _render_clock(self):
        year, month, day, _wd, hour, minute, second, _sub = self._rtc.datetime()
        if second == self._last_second:
            return
        self._last_second = second

        # write_line ignora linhas cujo conteúdo não mudou, então na prática
        # só a linha da hora vai ao display a cada segundo.
        self._lcd.write_line("{}, {:02d}/{:02d}/{:04d}".format(
            _weekday_name(year, month, day), day, month, year), row=0)
        self._lcd.write_line("{:02d}:{:02d}:{:02d}".format(hour, minute, second), row=1)
        self._lcd.write_line(self._temp_text(), row=2)
        self._lcd.write_line("Relogio ESP32 BLE", row=3)

    def _render_marquee(self):
        now = ticks_ms()
        if ticks_diff(now, self._marquee_start) >= self._marquee_duration_ms:
            self._stop_marquee()
            print("Modo Letreiro expirado, voltando ao Modo Normal")
            return
        if ticks_diff(now, self._marquee_last_scroll) < self._marquee_speed_ms:
            return
        self._marquee_last_scroll = now

        cols = config.LCD_COLS
        text = self._marquee_padded
        window = text[self._marquee_offset:self._marquee_offset + cols]
        if len(window) < cols:
            window += text[: cols - len(window)]
        for row in range(config.LCD_ROWS):
            self._lcd.write_line(window, row)
        self._marquee_offset = (self._marquee_offset + 1) % len(text)

    def _stop_marquee(self):
        self._marquee_active = False
        self._last_second = None  # força redesenho do relógio
        self._push_status()

    # ---- Status BLE ----

    def _service_status(self):
        if ticks_diff(ticks_ms(), self._last_status_ticks) >= _STATUS_REFRESH_MS:
            self._push_status()

    def _push_status(self):
        self._last_status_ticks = ticks_ms()
        status = {
            "mode": "marquee" if self._marquee_active else "normal",
            "connected": self._ble.is_connected(),
        }
        if self._last_temp_c is not None:
            status["temp_c"] = round(self._last_temp_c, 1)
        self._ble.set_status(status)

    # ---- Callbacks do BLE (executados no laço principal, não no IRQ) ----

    def _handle_set_datetime(self, data):
        unix_epoch = _as_int(data.get("epoch"), None)
        if unix_epoch is None or unix_epoch < _MIN_VALID_EPOCH:
            print("Epoch invalido ignorado:", data.get("epoch"))
            return
        year, month, day, hour, minute, second, wday0, _yday = localtime(
            unix_epoch - _UNIX_TO_MPY_EPOCH_OFFSET)
        self._rtc.datetime((year, month, day, wday0 + 1, hour, minute, second, 0))
        self._last_second = None
        print("SetDateTime recebido, RTC ajustado:", self._rtc.datetime())

    def _handle_marquee(self, data):
        text = data.get("text", "")
        if not isinstance(text, str):
            text = ""
        text = _sanitize(text)

        duration_s = _as_int(data.get("duration_s"), 30)
        speed_ms = _as_int(data.get("speed_ms"), 300)

        # Texto vazio ou duração não-positiva = pedido de cancelamento.
        if not text or duration_s <= 0:
            if self._marquee_active:
                self._stop_marquee()
            print("Letreiro cancelado pelo app.")
            return

        duration_s = min(duration_s, _MAX_DURATION_S)
        speed_ms = max(speed_ms, _MIN_SPEED_MS)

        cols = config.LCD_COLS
        # Espaços do tamanho do display nas pontas, para o texto entrar e
        # sair de cena em vez de "pular" direto na tela.
        self._marquee_padded = (" " * cols) + text + (" " * cols)
        self._marquee_offset = 0
        self._marquee_speed_ms = speed_ms
        self._marquee_duration_ms = duration_s * 1000
        self._marquee_start = ticks_ms()
        # ticks_add (e não subtração crua) por causa do wrap de ticks_ms.
        self._marquee_last_scroll = ticks_add(ticks_ms(), -speed_ms)
        self._marquee_active = True
        self._push_status()
        print("Modo Letreiro ativado:", text, duration_s, "s @", speed_ms, "ms")

    def _handle_config_write(self, data):
        unit = data.get("temp_unit")
        if unit in ("C", "F"):
            self._temp_unit = unit
            # Gravação em flash: segura aqui porque estamos no laço
            # principal, e não dentro do IRQ do BLE.
            storage.save_temp_unit(unit)
            self._ble.set_config({"temp_unit": unit})
            self._last_second = None  # força redesenho com a nova unidade
        print("Config recebido:", data)


def run():
    ClockApp().run()
