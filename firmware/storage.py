# Persistência de configurações (etapa 6 do roadmap) via NVS (Non-Volatile
# Storage) do ESP32 — ao contrário do RTC interno, sobrevive a
# reinícios/queda de energia (ver SPECS.md seção 3.3).
#
# Importante: gravar na NVS escreve na flash. Nunca chame save_*() de
# dentro de um handler de IRQ (ex: callback do BLE) — o laço principal é
# quem deve fazer isso. Ver comentário no topo de ble_service.py.

import esp32

VERSION = "storage v2 (tolerante a falha de NVS)"

_NAMESPACE = "relogio"
_KEY_TEMP_UNIT = "temp_unit"

try:
    _nvs = esp32.NVS(_NAMESPACE)
except Exception as e:  # pragma: no cover - depende do hardware
    print("NVS indisponivel, configuracoes nao serao persistidas:", e)
    _nvs = None


def load_temp_unit(default="C"):
    if _nvs is None:
        return default
    buf = bytearray(8)
    try:
        n = _nvs.get_blob(_KEY_TEMP_UNIT, buf)
        unit = bytes(buf[:n]).decode()
    except OSError:
        # Chave ainda não existe (primeira gravação / flash novo).
        return default
    except Exception as e:
        print("Falha ao ler config da NVS:", e)
        return default
    return unit if unit in ("C", "F") else default


def save_temp_unit(unit):
    if _nvs is None or unit not in ("C", "F"):
        return False
    try:
        _nvs.set_blob(_KEY_TEMP_UNIT, unit.encode())
        _nvs.commit()
        return True
    except Exception as e:
        print("Falha ao gravar config na NVS:", e)
        return False
