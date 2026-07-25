# Ponto de entrada autônomo: MicroPython roda "main.py" sozinho toda vez
# que o ESP32 recebe energia (USB na tomada/carregador/power bank), sem
# precisar do Thonny nem de computador conectado.
#
# Roda a aplicação completa — Modo Normal + Modo Letreiro + BLE — a mesma
# que test_ble.py. Não há mais data/hora chumbada aqui: como o RTC interno
# não tem bateria, ao ligar o relógio começa em 2000-01-01 e espera o app
# Android enviar a hora certa por BLE (botão "Sincronizar hora"). As
# configurações (unidade de temperatura) são lidas da NVS e sobrevivem ao
# desligamento.

import clock_app

clock_app.run()
