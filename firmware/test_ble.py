# Teste manual da aplicação completa (LCD + RTC interno + DS18B20 +
# serviço GATT + Modo Letreiro). Roda exatamente o mesmo código que o
# main.py autônomo — a diferença é só que você o dispara com F5 no Thonny
# e acompanha os prints no Shell.
#
# Use o app Android ou um app BLE genérico (ex: nRF Connect) para:
#   - SetDateTime (write): {"epoch": 1752500000}  (epoch Unix, segundos
#     desde 1970 — o mesmo que System.currentTimeMillis()/1000 no Android)
#     -> ajusta o RTC interno na hora.
#   - Marquee (write): {"text": "Bom dia!", "duration_s": 30, "speed_ms": 300}
#     -> ativa o Modo Letreiro: o texto rola nas 4 linhas pelo tempo
#     configurado e depois volta sozinho ao Modo Normal.
#     Para cancelar antes da hora: {"text": ""} ou {"duration_s": 0}.
#   - Config (read/write): {"temp_unit": "C"} ou {"temp_unit": "F"}
#     -> a escolha é gravada na NVS e sobrevive a reinícios.
#   - Status (read/notify): {"mode": "normal"|"marquee", "temp_c": ..., "connected": ...}
#
# Sem o DS18B20 conectado o relógio sobe normalmente: a linha 3 mostra
# "Sem sensor de temp." e o Status simplesmente não inclui "temp_c".

import clock_app

clock_app.run()
