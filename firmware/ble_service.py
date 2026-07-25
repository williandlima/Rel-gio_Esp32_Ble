# Serviço BLE GATT customizado (ver SPECS.md seção 4), usando o módulo
# `bluetooth` nativo do MicroPython (API de baixo nível, baseada em IRQ).
#
# Características (payloads sempre em JSON, codificado em UTF-8):
#   - SetDateTime (write):      {"epoch": 1752500000}
#   - Marquee     (write):      {"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}
#   - Config      (read/write): {"temp_unit": "C"}
#   - Status      (read/notify):{"mode": "normal", "temp_c": 24.5, "connected": true}
#
# Regra de ouro deste módulo: o handler de IRQ (_irq) nunca processa nada
# pesado — ele só enfileira os bytes recebidos. Parse de JSON, callbacks da
# aplicação e (principalmente) gravação em flash acontecem em tick(),
# chamado pelo laço principal. Gravar na NVS ou bloquear dentro do IRQ do
# NimBLE é o caminho mais curto para travar o ESP32.

import json
import bluetooth
from micropython import const
from utime import ticks_ms, ticks_diff

VERSION = "ble_service v5 (processamento fora do IRQ + buffers de 512B)"

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

# Tamanho do buffer interno de cada característica. O padrão do MicroPython
# é de apenas 20 bytes: qualquer escrita maior era truncada pelo próprio
# stack (independente do MTU negociado!) e uma leitura de Status devolvia
# JSON cortado no meio. Era esta a causa raiz da truncagem histórica.
_VALUE_BUFFER_SIZE = const(512)

# Se um novo fragmento demorar mais que isso para chegar, o que estava
# acumulado é considerado resto de uma mensagem perdida e é descartado —
# sem isso, lixo antigo contaminaria a próxima mensagem válida.
_FRAGMENT_TIMEOUT_MS = const(3000)

# Teto de eventos de escrita que o IRQ enfileira entre dois ticks.
_MAX_PENDING = const(16)

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
        print("Iniciando", VERSION)
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.config(mtu=256)
        self._ble.irq(self._irq)

        ((
            self._handle_set_datetime,
            self._handle_marquee,
            self._handle_config,
            self._handle_status,
        ),) = self._ble.gatts_register_services((_SERVICE,))

        for handle in (self._handle_set_datetime, self._handle_marquee,
                       self._handle_config, self._handle_status):
            self._ble.gatts_set_buffer(handle, _VALUE_BUFFER_SIZE)

        self._connections = set()

        # Callbacks a serem atribuídos por quem instanciar o serviço. São
        # chamados a partir de tick(), ou seja, no laço principal.
        self.on_set_datetime = None
        self.on_marquee = None
        self.on_config_write = None

        self._pending = []
        self._write_buffers = {}
        self._buffer_ticks = {}
        self._need_advertise = False

        self._adv_name = name.encode()
        self._advertise()

    # ---- Contexto de IRQ: só o mínimo indispensável ----

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            self._write_buffers.clear()
            self._buffer_ticks.clear()
            self._need_advertise = True
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if len(self._pending) < _MAX_PENDING:
                self._pending.append((value_handle, self._ble.gatts_read(value_handle)))

    # ---- Laço principal ----

    def tick(self):
        """Processa tudo que o IRQ enfileirou. Chamar no laço principal."""
        if self._need_advertise:
            self._need_advertise = False
            self._advertise()

        if not self._pending:
            return

        # Troca a lista inteira em vez de consumir item a item: se o IRQ
        # disparar no meio, ele escreve na lista antiga (já capturada) ou na
        # nova — em qualquer um dos casos nada se perde.
        items = self._pending
        self._pending = []
        for value_handle, raw in items:
            try:
                self._dispatch_json(value_handle, raw)
            except Exception as e:
                print("Erro ao processar escrita BLE:", e)

    def _dispatch_json(self, value_handle, raw):
        now = ticks_ms()
        buf = self._write_buffers.get(value_handle)
        if buf is not None:
            started = self._buffer_ticks.get(value_handle, now)
            if ticks_diff(now, started) > _FRAGMENT_TIMEOUT_MS:
                print("Fragmento BLE antigo descartado:", buf)
                buf = None
        buf = (buf or b"") + raw

        try:
            data = json.loads(buf)
        except ValueError:
            if len(buf) > _VALUE_BUFFER_SIZE:
                print("Payload BLE invalido/incompleto demais, descartando:", buf)
                self._write_buffers.pop(value_handle, None)
                self._buffer_ticks.pop(value_handle, None)
            else:
                # Ainda incompleto: falta pelo menos mais um pedaço.
                self._write_buffers[value_handle] = buf
                self._buffer_ticks[value_handle] = now
            return

        self._write_buffers.pop(value_handle, None)
        self._buffer_ticks.pop(value_handle, None)
        print("BLE write completo recebido:", buf)

        callback = self._callback_for(value_handle)
        if callback is not None:
            callback(data)

    def _callback_for(self, value_handle):
        if value_handle == self._handle_set_datetime:
            return self.on_set_datetime
        if value_handle == self._handle_marquee:
            return self.on_marquee
        if value_handle == self._handle_config:
            return self.on_config_write
        return None

    # ---- API da aplicação ----

    def set_status(self, status_dict):
        payload = json.dumps(status_dict).encode()
        self._ble.gatts_write(self._handle_status, payload)
        # Itera sobre uma cópia: uma desconexão pode alterar o set no meio.
        for conn_handle in tuple(self._connections):
            try:
                self._ble.gatts_notify(conn_handle, self._handle_status, payload)
            except OSError:
                pass

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

    def _advertise(self, interval_us=500000):
        payload = bytearray()
        payload += bytes((2, 0x01, 0x06))  # flags: general discoverable
        name = self._adv_name
        payload += bytes((len(name) + 1, 0x09)) + name
        try:
            self._ble.gap_advertise(interval_us, adv_data=payload)
        except OSError as e:
            # Logo após uma desconexão o stack às vezes ainda não está
            # pronto para reanunciar (OSError: -30). Tenta de novo no
            # próximo tick — antes isso era feito com um Timer, que alocava
            # memória em contexto de interrupção.
            print("Advertise adiado para o proximo tick:", e)
            self._need_advertise = True
