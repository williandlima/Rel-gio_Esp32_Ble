# Persistência de configurações (etapa 6 do roadmap) via NVS (Non-Volatile
# Storage) do ESP32 — ao contrário do RTC interno, sobrevive a
# reinícios/queda de energia (ver SPECS.md seção 3.3).

import esp32

VERSION = "storage v1"

_NAMESPACE = "relogio"
_KEY_TEMP_UNIT = "temp_unit"

_nvs = esp32.NVS(_NAMESPACE)


def load_temp_unit(default="C"):
    buf = bytearray(4)
    try:
        n = _nvs.get_blob(_KEY_TEMP_UNIT, buf)
    except OSError:
        # Ainda não foi salvo nenhuma vez (primeira gravação/flash novo).
        return default
    unit = bytes(buf[:n]).decode()
    return unit if unit in ("C", "F") else default


def save_temp_unit(unit):
    if unit not in ("C", "F"):
        return
    _nvs.set_blob(_KEY_TEMP_UNIT, unit.encode())
    _nvs.commit()
