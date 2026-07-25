# Lista dos arquivos que compõem uma instalação completa do relógio no
# ESP32. Usada tanto por package.py quanto por install.py, para as duas
# nunca divergirem sobre o que faz parte de uma instalação — se um novo
# módulo for adicionado ao firmware, basta atualizar esta lista.
#
# Não inclui os scripts de teste isolado (set_time.py, test_display.py,
# test_normal_mode.py, test_ble.py, test_ble_sem_sensor.py): são
# ferramentas de desenvolvimento, não fazem parte do relógio em si.

RELEASE_FILES = [
    "config.py",
    "lcd_hd44780.py",
    "ds18b20_sensor.py",
    "bigfont.py",
    "ble_service.py",
    "storage.py",
    "clock_app.py",
    "main.py",
]
