# Serviço BLE GATT customizado (ver SPECS.md seção 4), usando o módulo
# `bluetooth` nativo do MicroPython (API de baixo nível, baseada em IRQ).
#
# Características (payloads sempre em JSON, codificado em UTF-8):
#   - SetDateTime (write):      {"epoch": 1752500000}
#   - Marquee     (write):      {"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}
#   - Config      (read/write): {"temp_unit": "C"}
#   - Status      (read/notify):{"mode": "normal", "temp_c": 24.5, "connected": true}

import json
import bluetooth
from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_READ = bluetooth.FLAG_READ
_FLAG_WRITE = bluetooth.FLAG_WRITE
_FLAG_NOTIFY = bluetooth.FLAG_NOTIFY

_SERVICE_UUID = bluetooth.UUID("8da7ea58-d7a9-4740-899d-e790d280bbec")
_SET_DATETIME_UUID = bluetooth.UUID("05dbf463-f5f4-4b26-9432-a063782076d3")
_MARQUEE_UUID = bluetooth.UUID("361e7fd4-683a-49bc-a3ad-9d0e284db3c7")
_CONFIG_UUID = bluetooth.UUID("592e0d32-9975-435b-8986-1ab319153779")
_STATUS_UUID = bluetooth.UUID("8f86a231-9483-468f-b065-2082f2cadc88")

_CHAR_SET_DATETIME = (_SET_DATETIME_UUID, _FLAG_WRITE)
_CHAR_MARQUEE = (_MARQUEE_UUID, _FLAG_WRITE)
_CHAR_CONFIG = (_CONFIG_UUID, _FLAG_READ | _FLAG_WRITE)
_CHAR_STATUS = (_STATUS_UUID, _FLAG_READ | _FLAG_NOTIFY)

_SERVICE = (
    _SERVICE_UUID,
    (_CHAR_SET_DATETIME, _CHAR_MARQUEE, _CHAR_CONFIG, _CHAR_STATUS),
)


class ClockBLEService:
    def __init__(self, name="Relogio-ESP32"):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)

        ((
            self._handle_set_datetime,
            self._handle_marquee,
            self._handle_config,
            self._handle_status,
        ),) = self._ble.gatts_register_services((_SERVICE,))

        self._connections = set()

        # Callbacks a serem atribuídos por quem instanciar o serviço.
        self.on_set_datetime = None
        self.on_marquee = None
        self.on_config_write = None

        self._advertise(name)

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            raw = self._ble.gatts_read(value_handle)
            if value_handle == self._handle_set_datetime:
                self._dispatch_json(raw, self.on_set_datetime)
            elif value_handle == self._handle_marquee:
                self._dispatch_json(raw, self.on_marquee)
            elif value_handle == self._handle_config:
                self._dispatch_json(raw, self.on_config_write)

    def _dispatch_json(self, raw, callback):
        if callback is None:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            return  # payload inválido, ignora
        callback(data)

    def set_status(self, status_dict):
        payload = json.dumps(status_dict).encode()
        self._ble.gatts_write(self._handle_status, payload)
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle_status, payload)

    def set_config(self, config_dict):
        payload = json.dumps(config_dict).encode()
        self._ble.gatts_write(self._handle_config, payload)

    def is_connected(self):
        return len(self._connections) > 0

    def get_config(self):
        raw = self._ble.gatts_read(self._handle_config)
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def _advertise(self, name=None, interval_us=500000):
        payload = bytearray()
        payload += bytes((2, 0x01, 0x06))  # flags: general discoverable
        if name:
            self._adv_name = name.encode()
        name_bytes = self._adv_name
        payload += bytes((len(name_bytes) + 1, 0x09)) + name_bytes
        self._ble.gap_advertise(interval_us, adv_data=payload)
