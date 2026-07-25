# Mantido apenas por compatibilidade com o passo a passo antigo: hoje ele
# é idêntico ao test_ble.py.
#
# O firmware detecta o DS18B20 sozinho — sem sensor no barramento, o
# relógio sobe do mesmo jeito e a linha 3 do display mostra
# "Sem sensor de temp.". Não existe mais uma variante separada de código
# para rodar sem sensor (era ~100 linhas duplicadas, com risco de as duas
# versões divergirem em silêncio).

import clock_app

clock_app.run()
