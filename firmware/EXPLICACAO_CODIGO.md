# Explicação do firmware — linha por linha

Este documento explica **todo o código Python que roda dentro do ESP32**
(os 8 arquivos gravados pelo Thonny ou pelo `tools/install.py`), linha por
linha. A ideia é você conseguir ler o código-fonte de verdade
(`firmware/*.py`) ao lado deste documento e entender exatamente o que cada
parte faz e por quê.

Não cobre o app Android nem o protocolo BLE em si (isso já está no
`SPECS.md`) — o foco aqui é **o que roda dentro do relógio**.

## Como ler isto

- Python usa **indentação** (espaços no começo da linha) para marcar o que
  está "dentro" de quê — em vez de chaves `{ }` como em outras linguagens.
  Uma linha mais recuada que a anterior está "dentro" dela (dentro de uma
  função, de um `if`, de uma classe, etc.).
- `#` começa um comentário — o que vem depois na linha é só explicação
  pra quem lê o código, o MicroPython ignora completamente.
- `"""assim entre aspas triplas"""` é uma *docstring* — um comentário
  maior, geralmente logo abaixo de `def` ou `class`, documentando aquela
  função/classe.
- Este documento usa os nomes exatos das variáveis e funções do código —
  vale abrir o arquivo de verdade ao lado pra acompanhar os números de
  linha citados.

## Visão geral: quem chama quem

```
main.py
  └── clock_app.run()
        └── ClockApp()                    # monta tudo
              ├── lcd_hd44780.LCD4Bit      # controla o display
              ├── ds18b20_sensor.DS18B20   # lê a temperatura
              ├── bigfont                  # fonte do letreiro ampliado
              ├── storage                  # lê/grava configurações na NVS
              └── ble_service.ClockBLEService  # conversa com o app
        └── .run()                         # laço infinito do relógio
```

`main.py` é só um gatilho de 2 linhas. Toda a lógica de verdade mora em
`clock_app.py`, que usa os outros 6 módulos como ferramentas. Vamos por
ordem: dos módulos mais simples (peças isoladas) até `clock_app.py` (que
junta tudo), terminando em `main.py`.

---

## 1. `config.py` — pinagem

```python
1  # Configuração central de pinos, conforme SPECS.md (seção 2.2)
2
3  VERSION = "config v1"
4
5  # LCD NHD-0420E2Z-NSW-BBW - paralelo HD44780, modo 4 bits
6  LCD_RS = 13
7  LCD_E = 14
8  LCD_D4 = 27
9  LCD_D5 = 26
10 LCD_D6 = 25
11 LCD_D7 = 33
12 LCD_COLS = 20
13 LCD_ROWS = 4
14
15 # Sensor de temperatura DS18B20 (1-Wire)
16 ONEWIRE_DATA = 4
```

O arquivo mais simples do projeto: nenhuma função, nenhuma classe, só
**constantes** (variáveis que não mudam depois de definidas).

- **Linha 3**: `VERSION` é uma convenção usada em *todos* os arquivos
  deste firmware (ver `SPECS.md` seção 8) — uma string identificando a
  versão daquele módulo específico, impressa no Shell do Thonny ao
  iniciar, pra você conferir se o ESP32 está com o código esperado.
- **Linhas 6-11**: cada `LCD_xx` é o número do **pino GPIO** do ESP32
  ligado àquele sinal do display (RS, Enable, e os 4 bits de dados D4-D7).
  Esses números vêm direto da pinagem física (`SPECS.md` seção 2.2) — se
  um dia você mudar a fiação, é só editar aqui, e todo o resto do
  firmware usa essas constantes em vez de números soltos.
- **Linhas 12-13**: dimensões do display — 20 colunas, 4 linhas.
- **Linha 16**: o pino de dados do sensor DS18B20 (1-Wire — um único fio
  de dados, além de alimentação e terra).

---

## 2. `lcd_hd44780.py` — driver do display

Esse é o arquivo que "fala a língua" do controlador HD44780 (o chip
dentro do display de cristal líquido) usando só 4 fios de dados (modo "4
bits", mais econômico em pinos que o modo de 8 bits).

```python
1  # Driver HD44780 (paralelo, modo 4 bits) para MicroPython / ESP32
2  # Testado com display NHD-0420E2Z-NSW-BBW (20 colunas x 4 linhas)
3  #
4  # RW é fixado em GND no hardware (só escrita), por isso não é controlado aqui.
5
6  from machine import Pin
7  from utime import sleep_us, sleep_ms
8
9  VERSION = "lcd_hd44780 v3 (cache de linha + CGRAM)"
```

- **Linha 6**: `machine` é um módulo **nativo do MicroPython** (não existe
  no Python "normal" — só faz sentido rodando num microcontrolador).
  `Pin` representa um pino GPIO físico: dá pra ler ou escrever se ele está
  em nível alto (3.3V) ou baixo (0V).
- **Linha 7**: `utime` é o módulo de tempo do MicroPython (equivalente ao
  `time` do Python normal, mas com funções extras pensadas pra
  microcontrolador). `sleep_us`/`sleep_ms` pausam a execução por uma
  quantidade de microssegundos/milissegundos — necessário aqui porque o
  chip do display exige tempos mínimos entre comandos.

```python
11 _LCD_CLEAR = 0x01
12 _LCD_HOME = 0x02
13 _LCD_ENTRY_MODE = 0x06          # incrementa cursor, sem shift do display
14 _LCD_DISPLAY_ON = 0x0C          # display on, cursor off, blink off
15 _LCD_FUNCTION_SET_4BIT = 0x28   # 4 bits, 2 linhas (N=1), fonte 5x8
16 _LCD_SET_DDRAM_ADDR = 0x80
17 _LCD_SET_CGRAM_ADDR = 0x40
```

Esses são **comandos do controlador HD44780**, definidos no datasheet do
chip (todo display baseado nesse controlador entende esses mesmos
códigos). `0x01`, `0x0C`, etc. são números em **hexadecimal** (base 16) —
é só um jeito mais curto de escrever certos números binários; por
exemplo `0x0C` é o mesmo que `00001100` em binário. Cada bit dentro desses
comandos liga/desliga uma opção do display (cursor visível, piscar,
direção da escrita, etc.) — o nome da constante (`_LCD_DISPLAY_ON`, por
exemplo) já diz o que ela faz, sem precisar decorar os bits.

Um `_` no começo do nome (`_LCD_CLEAR`) é uma convenção Python: "isso é
uso interno deste arquivo, quem importa este módulo não deveria mexer
diretamente nisso".

```python
19 # Endereços iniciais de cada linha, padrão para displays 20x4 (controlador
20 # HD44780 só endereça 2 "linhas" internamente; linhas 3 e 4 usam offset).
21 _ROW_OFFSETS = (0x00, 0x40, 0x14, 0x54)
```

Curiosidade do hardware: o HD44780 só tem memória endereçada como se
fossem **2 linhas** de 40 caracteres. Um display físico de 4 linhas
"finge" ter 4 linhas dividindo essas 2 linhas internas ao meio — por
isso os endereços das linhas 3 e 4 (`0x14`, `0x54`) não são uma simples
continuação das linhas 1 e 2. Essa tabela é o "mapa" oficial (do
datasheet) de onde cada linha física começa na memória do chip.

### A classe `LCD4Bit`

```python
24 class LCD4Bit:
25     def __init__(self, rs_pin, e_pin, d4_pin, d5_pin, d6_pin, d7_pin,
26                  cols=20, rows=4):
```

Uma **classe** é um "molde" pra criar objetos que guardam estado (dados)
e têm comportamento (funções). `__init__` é o **construtor** — roda
automaticamente quando você escreve `LCD4Bit(...)` em algum lugar (isso
acontece em `clock_app.py`). `self` é como o objeto se refere a si mesmo
— toda função dentro de uma classe recebe `self` como primeiro parâmetro,
e é através dele que a função acessa os dados guardados naquele objeto
específico.

```python
27         self.cols = cols
28         self.rows = rows
29
30         self._rs = Pin(rs_pin, Pin.OUT, value=0)
31         self._e = Pin(e_pin, Pin.OUT, value=0)
32         self._data = [Pin(p, Pin.OUT, value=0)
33                       for p in (d4_pin, d5_pin, d6_pin, d7_pin)]
```

- **27-28**: guarda o tamanho do display no próprio objeto, pra usar
  depois em outras funções.
- **30-31**: cria os objetos `Pin` para os sinais **RS** (Register
  Select — diz ao chip se o que está sendo mandado é um comando ou um
  caractere pra exibir) e **E** (Enable — o "pulso" que diz ao chip
  "leia agora o que está nos fios de dados"). `Pin.OUT` configura o pino
  como saída (o ESP32 manda sinal pra ele, não o contrário);
  `value=0` começa com o pino em nível baixo.
- **32-33**: isso é uma ***list comprehension*** — um jeito compacto de
  criar uma lista aplicando a mesma operação pra cada item de outra
  lista. Equivale a escrever:
  ```python
  self._data = []
  for p in (d4_pin, d5_pin, d6_pin, d7_pin):
      self._data.append(Pin(p, Pin.OUT, value=0))
  ```
  Resultado: `self._data` é uma lista com os 4 pinos de dados (D4 a D7),
  na ordem certa.

```python
35         # Última linha escrita em cada row, para não regravar conteúdo
36         # idêntico: o barramento é bit-bang em 4 bits e escrever as 4
37         # linhas custa ~8ms. Com o cache, só a linha da hora é reescrita a
38         # cada segundo.
39         self._line_cache = [None] * rows
```

`[None] * rows` cria uma lista com `rows` (4) elementos, todos `None`
("nenhum valor ainda") — uma posição por linha do display, guardando o
último texto escrito ali. Essa é a otimização de performance: reescrever
o display inteiro a cada segundo seria lento (o protocolo de 4 bits é
"bit-bang", ou seja, cada bit é escrito manualmente por software, sem
acelerador de hardware) — com o cache, só a linha que realmente mudou
(normalmente só a da hora) é reenviada.

```python
41         self._init_display()
```

Termina o construtor chamando a função que faz a sequência de
inicialização do chip (explicada mais abaixo).

### Escrevendo bit a bit

```python
43     def _pulse_enable(self):
44         self._e.value(0)
45         sleep_us(1)
46         self._e.value(1)
47         sleep_us(1)
48         self._e.value(0)
49         sleep_us(50)
```

O HD44780 só "lê" os pinos de dados no instante em que o pino **E** faz
uma transição de alto pra baixo (uma borda de descida). Essa função gera
esse pulso: garante que E está em 0, sobe pra 1, espera 1 microssegundo
(tempo mínimo que os dados precisam estar estáveis antes do pulso),
desce de novo pra 0 (é aqui que o chip realmente "lê"), e espera 50
microssegundos — o tempo que o chip precisa pra processar internamente
antes do próximo comando.

```python
51     def _write_nibble(self, nibble):
52         for i in range(4):
53             self._data[i].value((nibble >> i) & 0x01)
54         self._pulse_enable()
```

Um **nibble** é meio byte (4 bits). Como só temos 4 fios de dados
(D4-D7), cada byte precisa ser mandado em **dois** nibbles (4 bits de
cada vez). Esta função manda um nibble:
- `for i in range(4)`: repete para i = 0, 1, 2, 3 (os 4 fios).
- `(nibble >> i) & 0x01`: extrai o bit número `i` do nibble.
  `>>` desloca os bits para a direita (`nibble >> i` "empurra" o bit `i`
  para a posição mais à direita); `& 0x01` ("E" bit a bit com
  `00000001`) isola só esse bit, descartando o resto — resultado é `0`
  ou `1`.
- `self._data[i].value(...)`: coloca esse bit no pino físico
  correspondente.
- Depois de setar os 4 fios, `_pulse_enable()` avisa o chip pra ler.

```python
56     def _write_byte(self, value, rs):
57         self._rs.value(rs)
58         self._write_nibble((value >> 4) & 0x0F)
59         self._write_nibble(value & 0x0F)
```

Manda um **byte** completo (8 bits) em dois nibbles:
- **57**: define se isso é um comando (`rs=0`) ou um caractere pra
  exibir (`rs=1`).
- **58**: `(value >> 4) & 0x0F` pega os 4 bits **mais significativos**
  (a metade "de cima" do byte) e manda primeiro.
- **59**: `value & 0x0F` pega os 4 bits **menos significativos** (a
  metade "de baixo") e manda depois. Essa ordem (nibble alto primeiro)
  é uma exigência do protocolo do HD44780.

```python
61     def _command(self, cmd):
62         self._write_byte(cmd, rs=0)
63
64     def _write_char(self, ch):
65         self._write_byte(ord(ch), rs=1)
```

Dois atalhos: `_command` manda um byte como comando (RS=0); `_write_char`
manda um caractere como dado a ser exibido (RS=1). `ord(ch)` converte um
caractere (tipo `"A"`) no seu código numérico (o HD44780 trabalha com
números, não com o conceito de "letra").

### Ligando o display do zero

```python
67     def _init_display(self):
68         sleep_ms(20)  # aguarda estabilização da alimentação do display
69
70         # Sequência de reset especial (datasheet HD44780): força o
71         # controlador, que liga em modo 8 bits, a entrar em modo 4 bits.
72         self._write_nibble(0x03)
73         sleep_ms(5)
74         self._write_nibble(0x03)
75         sleep_us(150)
76         self._write_nibble(0x03)
77         sleep_us(150)
78         self._write_nibble(0x02)  # agora em modo 4 bits
79         sleep_us(150)
80
81         self._command(_LCD_FUNCTION_SET_4BIT)
82         self._command(_LCD_DISPLAY_ON)
83         self.clear()
84         self._command(_LCD_ENTRY_MODE)
```

Esta é a receita **exata do datasheet** do HD44780 pra ligar o display
com segurança, não importa em que estado ele estava antes (é por isso
que essa sequência específica de `0x03, 0x03, 0x03, 0x02` funciona mesmo
que você reinicie o ESP32 sem desligar o display fisicamente). Depois
desse ritual, ele já está em modo 4 bits e dá pra usar os comandos
normais:
- **81**: confirma modo 4 bits, 2 linhas internas, fonte de caractere
  5x8 pixels.
- **82**: liga o display, sem cursor visível, sem piscar.
- **83**: limpa a tela (função explicada abaixo).
- **84**: configura o "modo de entrada" — o cursor avança
  automaticamente pra direita a cada caractere escrito (comportamento
  natural de escrita).

```python
86     def clear(self):
87         self._command(_LCD_CLEAR)
88         sleep_ms(2)  # comando de clear é mais lento
89         self._line_cache = [None] * self.rows
```

Manda o comando de limpar e espera 2ms (esse comando específico demora
mais que os outros pra internamente apagar toda a memória do chip). A
última linha também zera o cache (linha 39) — depois de limpar
fisicamente, o cache não pode mais "confiar" que sabe o que está na tela.

### O truque da CGRAM (caractere customizado)

```python
91     def create_char(self, index, bitmap):
92         """Grava um caractere próprio na CGRAM (índices 0..7).
...
99         index &= 0x07
100        self._command(_LCD_SET_CGRAM_ADDR | (index << 3))
101        for line in bitmap:
102            self._write_byte(line & 0x1F, rs=1)
103        # Volta o endereçamento para a DDRAM, senão a próxima escrita cairia
104        # na CGRAM em vez de na tela.
105        self._command(_LCD_SET_DDRAM_ADDR)
106        self._line_cache = [None] * self.rows
```

Além dos caracteres de fábrica (A-Z, números, etc.), o HD44780 permite
**desenhar até 8 caracteres customizados** numa memória separada chamada
CGRAM (Character Generator RAM) — cada um é uma grade de 5x8 pixels que
você define bit a bit. É assim que o Modo Letreiro Ampliado desenha o
"bloco cheio" usado como pixel (ver `bigfont.py` mais abaixo) — sem
depender de nenhum caractere pronto da ROM do chip (que varia entre
fabricantes).

- **99**: `index &= 0x07` garante que o índice fique entre 0 e 7 (só
  existem 8 posições de CGRAM). `&=` é "faz E bit a bit e guarda de
  volta na mesma variável".
- **100**: `index << 3` desloca o índice 3 bits pra esquerda (multiplica
  por 8) — é assim que o endereço de cada caractere customizado é
  calculado dentro da CGRAM (cada um ocupa 8 posições de memória, uma
  por linha do desenho). `|` (OU bit a bit) combina isso com o comando
  base de "endereçar CGRAM".
- **101-102**: `bitmap` é uma lista de 8 números (um por linha do
  desenho, 5 bits cada) — grava cada um na CGRAM como se fosse um
  caractere normal (`rs=1`).
- **105**: crucial — depois de mexer na CGRAM, o "cursor" de escrita do
  chip fica apontando pra lá. Se você não voltar explicitamente pra
  DDRAM (a memória normal de texto, onde o que aparece na tela mora),
  a próxima coisa que você tentar escrever no display iria parar dentro
  da CGRAM por engano.

### Posicionamento e escrita de texto

```python
108    def move_to(self, col, row):
109        row = min(row, self.rows - 1)
110        addr = _ROW_OFFSETS[row] + col
111        self._command(_LCD_SET_DDRAM_ADDR | addr)
```

Move o "cursor" de escrita para uma coluna/linha específica.
`min(row, self.rows - 1)` protege contra pedir uma linha que não existe
(por exemplo, `row=10` num display de 4 linhas vira `row=3`, a última
válida). Usa a tabela `_ROW_OFFSETS` (linha 21) pra converter linha+coluna
no endereço real de memória do chip.

```python
113    def putstr(self, text, col=0, row=0):
114        row = min(max(row, 0), self.rows - 1)
115        self.move_to(col, row)
116        for ch in text[: self.cols - col]:
117            self._write_char(ch)
118        # Escrita parcial/arbitrária: o cache da linha deixa de ser confiável.
119        self._line_cache[row] = None
```

Escreve uma string a partir de uma posição. `min(max(row, 0), ...)`
protege contra linha negativa **e** contra linha grande demais ao mesmo
tempo. `text[: self.cols - col]` **corta** a string pra não tentar
escrever além do fim da linha (por exemplo, se `col=18` num display de 20
colunas, só sobram 2 posições). O `for` escreve caractere por caractere.
Como essa função permite escrever em qualquer posição arbitrária (não
necessariamente a linha inteira), o cache daquela linha vira inválido
(`None`) — não dá mais pra confiar que ele reflete o que está na tela.

```python
121    def write_line(self, text, row, force=False):
122        # Escreve a linha inteira, preenchendo com espaços para apagar
123        # qualquer resíduo de conteúdo anterior mais longo.
124        # (preenchimento manual: MicroPython não tem str.ljust())
125        row = min(max(row, 0), self.rows - 1)
126        truncated = text[: self.cols]
127        line = truncated + " " * (self.cols - len(truncated))
128        if not force and self._line_cache[row] == line:
129            return
130        self.putstr(line, col=0, row=row)
131        self._line_cache[row] = line
```

Esta é a função que **todo o resto do firmware usa** pra mostrar texto
(nunca chamam `putstr` diretamente, exceto ela mesma).
- **126**: corta o texto pro tamanho da linha, se for maior.
- **127**: completa com espaços até o tamanho exato de uma linha —
  `" " * N` repete o caractere espaço N vezes. Isso garante que texto
  antigo mais comprido (ex: "Configuracoes" na tela anterior) não deixe
  "sobras" visíveis quando a linha nova for mais curta.
- **128-129**: o coração da otimização de performance — se o texto final
  é exatamente igual ao que já está em cache pra essa linha, **não faz
  nada** (retorna sem escrever). É assim que, no Modo Normal, só a linha
  do relógio (que muda a cada segundo) realmente é reenviada ao display;
  data e temperatura, que mudam bem menos, ficam de fora da maioria dos
  ciclos. `force=True` ignora essa checagem (útil se você suspeitar que
  o cache está errado por algum motivo).
- **130-131**: escreve de verdade e atualiza o cache com o que acabou de
  ser mostrado.

---

## 3. `ds18b20_sensor.py` — sensor de temperatura

```python
1  # Wrapper do sensor DS18B20 (1-Wire) usando os módulos onewire/ds18x20
2  # já inclusos no firmware MicroPython oficial para ESP32.
...
12 from machine import Pin
13 from micropython import const
14 from utime import sleep_ms, ticks_ms, ticks_diff
15 import onewire
16 import ds18x20
17
18 VERSION = "ds18b20_sensor v2 (leitura nao-bloqueante)"
19
20 _CONVERSION_MS = const(750)
```

- **13**: `micropython.const()` é uma otimização específica do
  MicroPython — avisa o compilador que aquele valor nunca muda, então
  ele pode ser "inline" no bytecode em vez de ocupar uma variável de
  verdade, economizando RAM (importante num microcontrolador com pouca
  memória).
- **15-16**: `onewire` e `ds18x20` são módulos que já vêm prontos dentro
  do firmware MicroPython oficial pra ESP32 — implementam o protocolo
  1-Wire (um fio só de dados) e a conversa específica com sensores da
  família DS18x20.
- **20**: o sensor real leva ~750ms pra converter a temperatura em um
  número — essa constante guarda esse tempo de espera mínimo.

```python
23 class DS18B20:
24     def __init__(self, data_pin):
25         self._ow = onewire.OneWire(Pin(data_pin))
26         self._ds = ds18x20.DS18X20(self._ow)
27         self._roms = []
28         self._conversion_started = None
29         self.rescan()
```

Ao criar o objeto: monta o barramento 1-Wire no pino informado, cria o
driver DS18X20 por cima dele, começa com a lista de sensores encontrados
vazia (`_roms` guarda o "endereço de fábrica" de cada sensor no
barramento — dá pra ter vários no mesmo fio, embora este projeto só use
um) e nenhuma conversão em andamento. Termina chamando `rescan()`.

```python
31     def rescan(self):
32         """Procura sensores no barramento. Retorna True se achou algum."""
33         try:
34             self._roms = self._ds.scan()
35         except Exception as e:
36             print("Falha ao varrer o barramento 1-Wire:", e)
37             self._roms = []
38         return self.available
```

`try/except` é o mecanismo do Python pra **capturar erros sem travar o
programa**: tenta rodar o que está dentro do `try`; se der algum erro
(`Exception`), em vez de o programa inteiro parar com uma mensagem de
erro, executa o que está dentro do `except` — aqui, só imprime um aviso
e garante que a lista fique vazia. Essa é a base da tolerância a falhas
deste módulo: um sensor desconectado, com fiação ruim, ou com erro de
comunicação **nunca derruba o relógio inteiro** (documentado no
cabeçalho do arquivo, linhas 9-10).

```python
40     @property
41     def available(self):
42         return len(self._roms) > 0
43
44     @property
45     def conversion_pending(self):
46         return self._conversion_started is not None
```

`@property` transforma uma função em algo que se **parece** com uma
variável comum na hora de usar — em vez de escrever `sensor.available()`
(com parênteses, chamando a função), quem usa escreve só
`sensor.available` (sem parênteses), como se fosse um atributo. É
puramente estético/conveniência de leitura; por trás continua sendo uma
função rodando toda vez que é consultada. `available` diz se há algum
sensor encontrado; `conversion_pending` diz se uma conversão de
temperatura está em andamento.

```python
48     def start_conversion(self):
49         """Dispara a conversão e retorna imediatamente."""
50         if not self._roms:
51             return False
52         try:
53             self._ds.convert_temp()
54         except Exception as e:
55             print("Falha ao iniciar conversao do DS18B20:", e)
56             self._conversion_started = None
57             return False
58         self._conversion_started = ticks_ms()
59         return True
```

Aqui está a peça-chave da versão "não-bloqueante": `convert_temp()`
manda o sensor **começar** a medir, mas a função **não espera** os 750ms
— só registra em `self._conversion_started` o instante (em milissegundos
desde o boot, via `ticks_ms()`) em que a conversão começou, e devolve o
controle imediatamente pra quem chamou. É isso que permite o relógio
continuar atualizando o display/BLE normalmente enquanto a temperatura
"cozinha" em segundo plano.

```python
61     def result_ready(self):
62         if self._conversion_started is None:
63             return False
64         return ticks_diff(ticks_ms(), self._conversion_started) >= _CONVERSION_MS
```

`ticks_diff(agora, antes)` calcula quantos milissegundos se passaram
desde que a conversão começou (é a forma "segura" de subtrair tempos no
MicroPython — `ticks_ms()` eventualmente estoura e volta a zero depois
de rodar tempo suficiente, e `ticks_diff` lida com isso corretamente; uma
subtração comum `agora - antes` quebraria nesse estouro). Se já passou o
tempo mínimo de conversão, o resultado está pronto pra ser lido.

```python
66     def read_result(self):
67         """Lê o resultado da conversão. Retorna °C ou None em caso de falha."""
68         self._conversion_started = None
69         if not self._roms:
70             return None
71         try:
72             return self._ds.read_temp(self._roms[0])
73         except Exception as e:
74             print("Falha ao ler o DS18B20:", e)
75             return None
```

Lê o valor já convertido do primeiro sensor encontrado
(`self._roms[0]`). Sempre marca a conversão como encerrada (linha 68),
mesmo se a leitura falhar — senão o sistema ficaria achando pra sempre
que uma conversão está pendente. Se algo der errado na leitura, devolve
`None` em vez de travar (quem chama, em `clock_app.py`, sabe lidar com
"não consegui ler agora").

```python
77     def read_celsius(self):
78         """Leitura bloqueante (~750ms), por conveniência em testes no REPL.
79         O laço principal usa a versão em duas etapas."""
80         if not self.start_conversion():
81             return None
82         sleep_ms(_CONVERSION_MS)
83         return self.read_result()
```

Uma versão "simples" (mas que trava por 750ms) das duas funções acima
juntas — útil só se você quiser testar o sensor manualmente no Shell do
Thonny sem se preocupar com laços de eventos. O `clock_app.py` **não**
usa esta função no funcionamento normal; ele usa `start_conversion()` +
`result_ready()` + `read_result()` separadamente, do jeito não-bloqueante.

---

## 4. `bigfont.py` — fonte de blocos do letreiro ampliado

```python
15 VERSION = "bigfont v3 (tira continua de pixels, para rolar como as demais)"
16
17 # Índice do caractere customizado usado como "pixel aceso". Evita o índice 0
18 # para não trafegar byte nulo nas strings.
19 BLOCK_INDEX = 1
20 BLOCK_BITMAP = (0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F)
21
22 _ON = chr(BLOCK_INDEX)
23 _OFF = " "
24
25 GLYPH_COLS = 5
26 GLYPH_ROWS = 4
```

- **19-20**: `BLOCK_INDEX` é a posição (1) da CGRAM (ver `create_char` em
  `lcd_hd44780.py`) onde este módulo espera que o "bloco cheio" esteja
  gravado. `BLOCK_BITMAP` é o desenho desse bloco: 8 linhas, cada uma
  `0x1F` (binário `00011111` — os 5 bits mais à direita ligados, que é a
  largura de um caractere do HD44780) — ou seja, um retângulo
  completamente preenchido.
- **22**: `chr(1)` converte o número 1 de volta pra caractere — ou seja,
  `_ON` é literalmente o caractere que, quando escrito na tela, mostra o
  bloco cheio da CGRAM (índice 1). É assim que a "fonte" deste arquivo
  desenha pixels acesos: colocando esse caractere especial na posição
  certa dentro da string que vai pro display.
- **23**: um espaço em branco representa "pixel apagado" (o HD44780 já
  entende espaço como "nada aceso").
- **25-26**: cada letra é desenhada numa grade de 5 colunas por 4 linhas.

```python
28 _GLYPHS = {
29     " ": ("     ", "     ", "     ", "     "),
30     "A": (".###.", "#...#", "#####", "#...#"),
...
92 }
```

Um **dicionário** Python (`{chave: valor, ...}`) — a estrutura de dados
que mapeia cada caractere (a "chave", ex: `"A"`) pra um "desenho" (o
"valor": uma tupla de 4 strings, uma por linha do glifo). Nesses
desenhos, `#` significa pixel aceso e `.` significa apagado — é
literalmente uma arte em texto de como cada letra/número/símbolo deve
aparecer, célula por célula.

```python
94 _FALLBACK = _GLYPHS["?"]
95
96
97 def has_glyph(ch):
98     return ch.upper() in _GLYPHS
```

Se um caractere pedido não existir no dicionário (por exemplo, um
símbolo mais raro), usa o desenho de `"?"` como substituto — em vez de
travar com um erro de "chave não encontrada". `ch.upper()` converte pra
maiúscula antes de checar — o dicionário só tem entradas maiúsculas, e
esse é o jeito de aceitar letras minúsculas também (`"a"` vira `"A"`
antes de procurar).

```python
101 def render_strip(text, rows=GLYPH_ROWS, scale=4, gap=1):
102     """Monta `rows` strings com o texto inteiro concatenado em pixels
...
108     strips = [""] * rows
109     gap_blank = _OFF * (gap * scale)
110     for ch in text:
111         glyph = _GLYPHS.get(ch.upper(), _FALLBACK)
112         for row in range(rows):
113             bits = glyph[row] if row < len(glyph) else _OFF * GLYPH_COLS
114             expanded = "".join((_ON if c == "#" else _OFF) * scale for c in bits)
115             strips[row] += expanded + gap_blank
116     return strips
```

A função mais importante deste arquivo: transforma um texto inteiro
(ex: `"OI"`) em 4 strings compridas — uma "tira" contínua de pixels, uma
por linha do display —, que depois `clock_app.py` desliza pela tela
(rolando), exatamente como faz com um texto normal no Modo Rolagem.

- **108**: começa com 4 strings vazias, uma por linha.
- **109**: quantidade de espaço em branco entre um caractere e o
  próximo, escalado pro mesmo tamanho dos pixels.
- **110**: para cada caractere do texto recebido...
- **111**: busca o desenho dele no dicionário (ou usa o `_FALLBACK`).
- **112-115**: para cada uma das 4 linhas do desenho: pega os 5
  caracteres daquela linha do glifo (`.`/`#`), e para cada um deles gera
  `scale` cópias do caractere `_ON` (se for `#`) ou `_OFF` (se for `.`) —
  é assim que 1 "pixel" do desenho vira várias colunas reais do display
  (com `scale=2`, cada pixel do desenho vira 2 colunas de verdade, então
  a letra fica maior/mais grossa que o texto comum). `"".join(... for c
  in bits)` é outra list comprehension, só que já juntando tudo numa
  string só. O resultado dessa linha (mais o espaço de respiro) é
  **acrescentado** (`+=`) à tira daquela linha — por isso o resultado
  final é uma tira comprida com todos os caracteres do texto, um do lado
  do outro.
- **116**: devolve as 4 tiras completas.

---

## 5. `storage.py` — configurações que sobrevivem a reinício

```python
9  import esp32
...
13 _NAMESPACE = "relogio"
14 _KEY_TEMP_UNIT = "temp_unit"
15
16 try:
17     _nvs = esp32.NVS(_NAMESPACE)
18 except Exception as e:  # pragma: no cover - depende do hardware
19     print("NVS indisponivel, configuracoes nao serao persistidas:", e)
20     _nvs = None
```

`esp32.NVS` é a interface do MicroPython pra **NVS** (Non-Volatile
Storage) — uma área da memória flash do ESP32 reservada especificamente
pra guardar pequenas configurações que sobrevivem a reinícios e quedas de
energia (ao contrário da RAM comum, e ao contrário do RTC interno, que
não tem bateria). `_NAMESPACE` é como um "gaveta" dentro da NVS — separa
as configurações deste projeto de qualquer outra coisa que
eventualmente use a NVS. Se por algum motivo a NVS não estiver
disponível (hardware ou build de MicroPython sem suporte), o `try/except`
evita que o firmware inteiro quebre só por causa disso — `_nvs` fica
`None`, e as funções abaixo checam isso antes de usar.

```python
23 def load_temp_unit(default="C"):
24     if _nvs is None:
25         return default
26     buf = bytearray(8)
27     try:
28         n = _nvs.get_blob(_KEY_TEMP_UNIT, buf)
29         unit = bytes(buf[:n]).decode()
30     except OSError:
31         # Chave ainda não existe (primeira gravação / flash novo).
32         return default
33     except Exception as e:
34         print("Falha ao ler config da NVS:", e)
35         return default
36     return unit if unit in ("C", "F") else default
```

- **26**: `bytearray(8)` cria um "balde" de 8 bytes vazios, pra receber o
  que estiver gravado na NVS.
- **28**: `get_blob` lê o valor gravado sob a chave `"temp_unit"` para
  dentro desse balde, e devolve quantos bytes de fato foram lidos (`n`)
  — importante porque o valor real (`"C"` ou `"F"`) tem só 1 byte, bem
  menor que o balde de 8.
- **29**: `buf[:n]` pega só os bytes realmente escritos (descarta o resto
  do balde, que ficou "sujo"/não usado); `bytes(...)` e `.decode()`
  convertem esses bytes de volta pra uma string de texto normal.
- **30-32**: se a chave nunca foi gravada (ESP32 recém-flashado, nunca
  configurado antes), `get_blob` levanta `OSError` — nesse caso, devolve
  o valor padrão (`"C"`) sem drama.
- **36**: checagem final de sanidade — só aceita `"C"` ou `"F"`; qualquer
  outra coisa (dado corrompido, por exemplo) cai no padrão.

```python
39 def save_temp_unit(unit):
40     if _nvs is None or unit not in ("C", "F"):
41         return False
42     try:
43         _nvs.set_blob(_KEY_TEMP_UNIT, unit.encode())
44         _nvs.commit()
45         return True
46     except Exception as e:
47         print("Falha ao gravar config na NVS:", e)
48         return False
```

`unit.encode()` converte a string (`"C"` ou `"F"`) em bytes (formato que
a NVS entende). `set_blob` grava; `commit()` garante que a gravação
realmente foi persistida na flash (sem isso, poderia ficar só num buffer
temporário e se perder se a energia caísse logo em seguida).

---

## 6. `ble_service.py` — o servidor Bluetooth

Este é o módulo mais delicado do projeto — a parte que conversa com o
app Android. O comentário no topo do arquivo resume a regra mais
importante dele:

```python
10 # Regra de ouro deste módulo: o handler de IRQ (_irq) nunca processa nada
11 # pesado — ele só enfileira os bytes recebidos. Parse de JSON, callbacks da
12 # aplicação e (principalmente) gravação em flash acontecem em tick(),
13 # chamado pelo laço principal. Gravar na NVS ou bloquear dentro do IRQ do
14 # NimBLE é o caminho mais curto para travar o ESP32.
```

Uma **IRQ** (interrupt request, "pedido de interrupção") é um mecanismo
de hardware: quando algo acontece (chegou um pacote Bluetooth, por
exemplo), o processador **pausa** o que estava fazendo e corre pra
executar uma função especial (o "handler" da interrupção) — e só depois
volta pro que estava fazendo antes. Esse handler precisa ser **rapidíssimo**:
se ele demorar (ou pior, travar), toda a pilha de Bluetooth do sistema
(chamada NimBLE no ESP32) pode ficar instável ou travar de vez. Por isso
a estratégia deste arquivo é: a função de IRQ só guarda ("enfileira") os
dados recebidos numa lista, e todo o processamento de verdade (entender
o JSON, chamar as funções da aplicação, gravar configurações) acontece
depois, chamado explicitamente pelo laço principal do programa (função
`tick()`).

```python
16 import json
17 import bluetooth
18 from micropython import const
19 from utime import ticks_ms, ticks_diff
20
21 VERSION = "ble_service v5 (processamento fora do IRQ + buffers de 512B)"
22
23 _IRQ_CENTRAL_CONNECT = const(1)
24 _IRQ_CENTRAL_DISCONNECT = const(2)
25 _IRQ_GATTS_WRITE = const(3)
```

- **16**: `json` converte entre texto JSON (`'{"epoch": 123}'`) e
  estruturas de dados Python (dicionários, listas, números) — nos dois
  sentidos (`json.loads` lê texto → Python; `json.dumps` faz o
  contrário).
- **17**: `bluetooth` é o módulo **nativo do MicroPython** que dá acesso
  de baixo nível ao rádio Bluetooth Low Energy do ESP32.
- **23-25**: códigos numéricos que o módulo `bluetooth` usa pra
  identificar cada tipo de evento (conexão de um celular, desconexão,
  escrita numa característica) — vêm da documentação oficial do
  MicroPython, são sempre esses números fixos.

```python
27 # Tamanho do buffer interno de cada característica. O padrão do MicroPython
28 # é de apenas 20 bytes: qualquer escrita maior era truncada pelo próprio
29 # stack (independente do MTU negociado!) e uma leitura de Status devolvia
30 # JSON cortado no meio. Era esta a causa raiz da truncagem histórica.
31 _VALUE_BUFFER_SIZE = const(512)
32
33 # Se um novo fragmento demorar mais que isso para chegar, o que estava
34 # acumulado é considerado resto de uma mensagem perdida e é descartado —
35 # sem isso, lixo antigo contaminaria a próxima mensagem válida.
36 _FRAGMENT_TIMEOUT_MS = const(3000)
37
38 # Teto de eventos de escrita que o IRQ enfileira entre dois ticks.
39 _MAX_PENDING = const(16)
```

Três limites de segurança explicados nos próprios comentários — vale
notar que `_VALUE_BUFFER_SIZE` (512 bytes) foi literalmente a correção de
um bug real deste projeto: o MicroPython, por padrão, só reserva 20
bytes de memória por característica BLE — qualquer coisa maior que isso
era cortada **antes mesmo de chegar** no nosso código (ver
`gatts_set_buffer` mais abaixo, linhas 77-79).

```python
45 _SERVICE_UUID = bluetooth.UUID("8da7ea58-d7a9-4740-899d-e790d280bbec")
46 _SET_DATETIME_UUID = bluetooth.UUID("05dbf463-f5f4-4b26-9432-a063782076d3")
47 _MARQUEE_UUID = bluetooth.UUID("361e7fd4-683a-49bc-a3ad-9d0e284db3c7")
48 _CONFIG_UUID = bluetooth.UUID("592e0d32-9975-435b-8986-1ab319153779")
49 _STATUS_UUID = bluetooth.UUID("8f86a231-9483-468f-b065-2082f2cadc88")
```

Um **UUID** (Universally Unique Identifier) é um número gigante,
praticamente impossível de colidir por acaso com outro, usado como
"nome" único pra cada serviço/característica Bluetooth. Esses valores
específicos foram gerados uma vez para este projeto (ver `SPECS.md`
seção 4.2) e precisam ser **idênticos** entre firmware e app Android —
é assim que o app sabe "essa característica aqui é a de ajustar a
hora", por exemplo.

```python
51 _CHAR_SET_DATETIME = (_SET_DATETIME_UUID, _FLAG_WRITE)
52 _CHAR_MARQUEE = (_MARQUEE_UUID, _FLAG_WRITE)
53 _CHAR_CONFIG = (_CONFIG_UUID, _FLAG_READ | _FLAG_WRITE)
54 _CHAR_STATUS = (_STATUS_UUID, _FLAG_READ | _FLAG_NOTIFY)
55
56 _SERVICE = (
57     _SERVICE_UUID,
58     (_CHAR_SET_DATETIME, _CHAR_MARQUEE, _CHAR_CONFIG, _CHAR_STATUS),
59 )
```

Cada característica é definida como uma **tupla** (`(a, b)` — uma lista
que não pode ser alterada depois de criada) juntando seu UUID com as
permissões que ela tem: `SetDateTime` e `Marquee` só aceitam escrita
(`_FLAG_WRITE`); `Config` aceita leitura **e** escrita (`|` = "OU bit a
bit", combina as duas permissões); `Status` aceita leitura e
notificação (o servidor consegue avisar o app proativamente quando o
valor muda, sem o app precisar ficar perguntando). `_SERVICE` junta tudo
num pacote só, no formato que a API `bluetooth` do MicroPython espera
receber.

### A classe `ClockBLEService`

```python
62 class ClockBLEService:
63     def __init__(self, name="Relogio-ESP32"):
64         print("Iniciando", VERSION)
65         self._ble = bluetooth.BLE()
66         self._ble.active(True)
67         self._ble.config(mtu=256)
68         self._ble.irq(self._irq)
```

- **65-66**: cria o objeto de controle do rádio Bluetooth e liga ele.
- **67**: negocia um **MTU** (Maximum Transmission Unit, tamanho máximo
  de pacote) de até 256 bytes — o padrão do Bluetooth é só 23 bytes,
  pequeno demais pra um JSON típico deste projeto.
- **68**: registra `self._irq` (função definida mais abaixo) como a
  função que o MicroPython deve chamar sempre que acontecer qualquer
  evento Bluetooth (conexão, desconexão, escrita, etc.).

```python
70         ((
71             self._handle_set_datetime,
72             self._handle_marquee,
73             self._handle_config,
74             self._handle_status,
75         ),) = self._ble.gatts_register_services((_SERVICE,))
```

`gatts_register_services` cadastra o serviço Bluetooth de verdade no
rádio, e devolve um "handle" (um número identificador interno) pra cada
característica — esses handles são o que se usa depois pra ler/escrever
valores. A sintaxe com parênteses duplos e vírgula
(`((a, b, c, d),) = ...`) é **desempacotamento**: a função devolve uma
lista com um serviço, contendo uma lista com 4 handles — essa linha
"abre" essa estrutura e guarda cada handle já na variável certa
(`self._handle_set_datetime`, etc.), tudo numa linha só.

```python
77         for handle in (self._handle_set_datetime, self._handle_marquee,
78                        self._handle_config, self._handle_status):
79             self._ble.gatts_set_buffer(handle, _VALUE_BUFFER_SIZE)
```

Este `for` percorre os 4 handles e, pra cada um, chama
`gatts_set_buffer` aumentando o buffer interno daquela característica
de 20 bytes (padrão) para 512 (`_VALUE_BUFFER_SIZE`, linha 31) — a
correção do bug de truncagem mencionado antes.

```python
81         self._connections = set()
82
83         # Callbacks a serem atribuídos por quem instanciar o serviço. São
84         # chamados a partir de tick(), ou seja, no laço principal.
85         self.on_set_datetime = None
86         self.on_marquee = None
87         self.on_config_write = None
88
89         self._pending = []
90         self._write_buffers = {}
91         self._buffer_ticks = {}
92         self._need_advertise = False
93
94         self._adv_name = name.encode()
95         self._advertise()
```

- **81**: um `set()` (conjunto) guarda os "handles de conexão" dos
  celulares atualmente conectados — um `set` nunca tem itens repetidos e
  é rápido pra adicionar/remover, ideal aqui.
- **85-87**: três "ganchos" que começam vazios (`None`). Quem cria o
  `ClockBLEService` (no caso, `clock_app.py`) preenche essas variáveis
  depois com as funções que devem ser chamadas quando cada tipo de
  mensagem chegar — um padrão comum em Python chamado *callback*.
- **89-92**: as estruturas de dados da "fila de processamento" (fila de
  eventos pendentes, buffers de remontagem de fragmentos, controle de
  timeout, flag de reanunciar) — todas explicadas em detalhe nas funções
  abaixo.
- **94-95**: guarda o nome que vai aparecer no Bluetooth do celular
  (`"Relogio-ESP32"`) já convertido pra bytes, e começa a anunciar.

```python
99     def _irq(self, event, data):
100        if event == _IRQ_CENTRAL_CONNECT:
101            conn_handle, _, _ = data
102            self._connections.add(conn_handle)
102        elif event == _IRQ_CENTRAL_DISCONNECT:
104            conn_handle, _, _ = data
105            self._connections.discard(conn_handle)
106            self._write_buffers.clear()
107            self._buffer_ticks.clear()
108            self._need_advertise = True
109        elif event == _IRQ_GATTS_WRITE:
110            conn_handle, value_handle = data
111            if len(self._pending) < _MAX_PENDING:
112                self._pending.append((value_handle, self._ble.gatts_read(value_handle)))
```

A função de interrupção — chamada automaticamente pelo MicroPython, sem
que o resto do código precise "pedir". Repare como cada `if`/`elif`
faz **muito pouco trabalho**, seguindo a regra de ouro do topo do
arquivo:
- **Conexão** (100-102): adiciona o identificador da nova conexão ao
  conjunto. `conn_handle, _, _ = data` desempacota os 3 valores que
  vêm junto do evento — o `_` é convenção Python pra "esse valor eu
  recebo mas não uso", só o primeiro (`conn_handle`) importa aqui.
- **Desconexão** (103-108): remove essa conexão do conjunto
  (`discard` — como `remove`, mas não dá erro se o item já não estiver
  lá), limpa qualquer fragmento de mensagem incompleto que estivesse
  esperando mais dados daquele celular (se ele desconectou no meio de
  uma escrita, esses restos não servem mais pra nada), e marca que
  precisa **reanunciar** — depois de uma desconexão o relógio precisa
  voltar a ficar "visível" pra outros celulares se conectarem.
- **Escrita numa característica** (109-112): em vez de processar o dado
  ali mesmo (proibido pela regra de ouro), só guarda numa lista de
  pendências (`self._pending.append(...)`) o handle da característica e
  os bytes recebidos (`gatts_read` busca o valor bruto que acabou de ser
  escrito). O `if len(...) < _MAX_PENDING` é um limite de segurança —
  se por algum motivo chegarem escritas mais rápido do que o laço
  principal consegue processar, essa fila não cresce sem limite (o que
  poderia estourar a memória).

```python
116    def tick(self):
117        """Processa tudo que o IRQ enfileirou. Chamar no laço principal."""
118        if self._need_advertise:
119            self._need_advertise = False
120            self._advertise()
121
122        if not self._pending:
123            return
124
125        # Troca a lista inteira em vez de consumir item a item: se o IRQ
126        # disparar no meio, ele escreve na lista antiga (já capturada) ou na
127        # nova — em qualquer um dos casos nada se perde.
128        items = self._pending
129        self._pending = []
130        for value_handle, raw in items:
131            try:
132                self._dispatch_json(value_handle, raw)
133            except Exception as e:
134                print("Erro ao processar escrita BLE:", e)
```

Esta função **precisa** ser chamada repetidamente pelo laço principal do
programa (é o que `clock_app.py` faz, a cada volta do laço) — é aqui
que o trabalho "pesado" de verdade acontece, fora do contexto de
interrupção.
- **118-120**: se ficou marcado que precisa reanunciar (por exemplo,
  depois de uma desconexão), tenta de novo agora.
- **122-123**: se não há nada pendente, não faz nada (sai cedo — um
  padrão comum chamado *early return*, evita indentar o resto da função
  dentro de um `if`).
- **125-129**: um detalhe sutil de concorrência — troca a lista inteira
  por uma nova vazia, em vez de ficar removendo item por item enquanto
  processa. Isso importa porque a IRQ pode disparar **a qualquer
  momento**, inclusive no meio dessa função — se a troca não fosse
  atômica desse jeito, um novo item poderia ser perdido ou processado
  fora de ordem.
- **130-134**: processa cada item enfileirado, um por vez, protegido por
  `try/except` — se um payload específico der problema ao processar
  (JSON maluco, por exemplo), só aquele item falha e é logado; o laço
  principal do relógio continua rodando normalmente pros próximos.

```python
136    def _dispatch_json(self, value_handle, raw):
137        now = ticks_ms()
138        buf = self._write_buffers.get(value_handle)
139        if buf is not None:
140            started = self._buffer_ticks.get(value_handle, now)
141            if ticks_diff(now, started) > _FRAGMENT_TIMEOUT_MS:
142                print("Fragmento BLE antigo descartado:", buf)
143                buf = None
144        buf = (buf or b"") + raw
```

Isso resolve um problema real do Bluetooth no Android: o app às vezes
precisa mandar uma mensagem maior que cabe num único pacote, então
divide em **pedaços** e manda um atrás do outro (ver explicação de
"transmissão serial" dada antes nesta conversa). Esta função vai
remontando esses pedaços:
- **138**: `.get(value_handle)` busca se já existe um pedaço acumulado
  daquela característica específica (devolve `None` se não existir —
  diferente de usar `[value_handle]` direto, que daria erro se a chave
  não existisse ainda).
- **139-143**: se já havia algo acumulado, mas o **último** pedaço
  chegou há mais de 3 segundos (`_FRAGMENT_TIMEOUT_MS`), descarta —
  presume-se que o resto da mensagem se perdeu (por exemplo, o celular
  desconectou no meio) e não vale a pena continuar esperando
  indefinidamente por um pedaço que talvez nunca chegue.
- **144**: `buf or b""` — se `buf` for `None`, usa bytes vazios no
  lugar; concatena com o pedaço novo (`raw`) recém-recebido.

```python
146        try:
147            data = json.loads(buf)
148        except ValueError:
149            if len(buf) > _VALUE_BUFFER_SIZE:
150                print("Payload BLE invalido/incompleto demais, descartando:", buf)
151                self._write_buffers.pop(value_handle, None)
152                self._buffer_ticks.pop(value_handle, None)
153            else:
154                # Ainda incompleto: falta pelo menos mais um pedaço.
155                self._write_buffers[value_handle] = buf
156                self._buffer_ticks[value_handle] = now
157            return
```

Tenta interpretar o que já foi acumulado como um JSON completo.
- **148**: se `json.loads` falhar (`ValueError` — texto incompleto ou
  mal formado), significa que **ainda falta** pelo menos mais um
  pedaço — isso é esperado no meio de uma transmissão fragmentada, não
  é necessariamente um erro real.
- **149-152**: só desiste de vez se já acumulou mais bytes que o buffer
  máximo permitido (512) sem nunca formar um JSON válido — nesse caso, é
  mesmo lixo, descarta tudo daquela característica.
- **154-156**: caso contrário, guarda o que tem até agora e espera o
  próximo pedaço chegar (na próxima chamada desta função, vai
  concatenar com o que já está salvo aqui, na linha 138).

```python
159        self._write_buffers.pop(value_handle, None)
160        self._buffer_ticks.pop(value_handle, None)
161        print("BLE write completo recebido:", buf)
162
163        callback = self._callback_for(value_handle)
164        if callback is not None:
165            callback(data)
```

Se chegou até aqui, `json.loads` **funcionou** — a mensagem está
completa. Limpa os buffers de remontagem daquela característica
(`.pop(chave, None)` remove se existir, sem dar erro se não existir) e
chama a função de callback correspondente (definida pelo `clock_app.py`),
passando o dado já interpretado (um dicionário Python, não mais texto
JSON cru).

```python
167    def _callback_for(self, value_handle):
168        if value_handle == self._handle_set_datetime:
169            return self.on_set_datetime
170        if value_handle == self._handle_marquee:
171            return self.on_marquee
172        if value_handle == self._handle_config:
173            return self.on_config_write
174        return None
```

Função auxiliar simples: dado o handle de uma característica, devolve
qual dos 3 callbacks (`on_set_datetime`, `on_marquee`,
`on_config_write`) deve ser chamado.

```python
178    def set_status(self, status_dict):
179        payload = json.dumps(status_dict).encode()
180        self._ble.gatts_write(self._handle_status, payload)
181        # Itera sobre uma cópia: uma desconexão pode alterar o set no meio.
182        for conn_handle in tuple(self._connections):
183            try:
184                self._ble.gatts_notify(conn_handle, self._handle_status, payload)
185            except OSError:
186                pass
```

Chamada pelo `clock_app.py` sempre que o status do relógio muda (modo
normal/letreiro, temperatura, conectado). `json.dumps` converte o
dicionário Python de volta pra texto JSON; `.encode()` converte esse
texto em bytes. `gatts_write` atualiza o valor "estático" da
característica (o que um app leria se pedisse pra ler agora), e o `for`
manda uma **notificação ativa** pra cada celular conectado — ou seja, o
relógio avisa o app proativamente, sem o app precisar ficar perguntando
toda hora. `tuple(self._connections)` faz uma cópia da lista de conexões
antes de percorrer — necessário porque, em teoria, uma desconexão
(que mexe nesse mesmo conjunto) poderia acontecer bem no meio deste
`for`, e mexer numa lista enquanto ela está sendo percorrida é
perigoso/gera erro em Python.

```python
188    def set_config(self, config_dict):
189        payload = json.dumps(config_dict).encode()
190        self._ble.gatts_write(self._handle_config, payload)
191
192    def is_connected(self):
193        return len(self._connections) > 0
194
195    def get_config(self):
196        raw = self._ble.gatts_read(self._handle_config)
197        try:
198            return json.loads(raw)
199        except ValueError:
200            return {}
```

Funções auxiliares simples de leitura/escrita usadas pelo
`clock_app.py`: `set_config` atualiza o valor exposto na característica
Config; `is_connected` diz se há pelo menos uma conexão ativa;
`get_config` lê de volta o que está gravado ali (devolve um dicionário
vazio se, por algum motivo, o conteúdo não for um JSON válido).

```python
202    def _advertise(self, interval_us=500000):
203        payload = bytearray()
204        payload += bytes((2, 0x01, 0x06))  # flags: general discoverable
205        name = self._adv_name
206        payload += bytes((len(name) + 1, 0x09)) + name
207        try:
208            self._ble.gap_advertise(interval_us, adv_data=payload)
209        except OSError as e:
210            # Logo após uma desconexão o stack às vezes ainda não está
211            # pronto para reanunciar (OSError: -30). Tenta de novo no
212            # próximo tick — antes isso era feito com um Timer, que alocava
213            # memória em contexto de interrupção.
214            print("Advertise adiado para o proximo tick:", e)
215            self._need_advertise = True
```

Monta manualmente o "pacote de anúncio" Bluetooth (o que faz o relógio
aparecer na lista de dispositivos do celular quando você escaneia). Esse
pacote segue um formato específico do padrão Bluetooth (cada "pedaço"
começa com o tamanho, seguido de um código do tipo de informação, e o
conteúdo): primeiro as *flags* (linha 204, dizendo "sou detectável
publicamente"), depois o nome do dispositivo (linhas 205-206). Se o
rádio ainda não estiver pronto pra anunciar de novo (comum logo depois
de uma desconexão — erro `-30`), em vez de travar ou tentar de novo
imediatamente (o que poderia alocar memória dentro de uma interrupção,
perigoso), só marca `_need_advertise = True` e deixa a próxima chamada
de `tick()` (no laço principal) tentar de novo.

---

## 7. `clock_app.py` — a aplicação

Este é o arquivo que **junta tudo**: usa o display, o sensor, o serviço
Bluetooth e a persistência para implementar o comportamento completo do
relógio.

```python
15 from machine import RTC
16 from utime import sleep_ms, ticks_ms, ticks_add, ticks_diff, localtime
17
18 import config
19 import lcd_hd44780
20 import ble_service
21 import storage
22 import bigfont
23 from lcd_hd44780 import LCD4Bit
24 from ble_service import ClockBLEService
25
26 VERSION = "clock_app v4 (Modo Ampliado menos exagerado)"
```

- **15**: `RTC` é o **relógio de tempo real interno** do ESP32 — guarda
  data/hora enquanto o chip está ligado (sem bateria própria: perde tudo
  ao desligar).
- **18-24**: importa todos os outros módulos deste projeto. Repare que
  alguns são importados de duas formas: `import lcd_hd44780` (pra poder
  usar `lcd_hd44780.VERSION` na linha 112) **e**
  `from lcd_hd44780 import LCD4Bit` (pra poder escrever só `LCD4Bit(...)`
  em vez de `lcd_hd44780.LCD4Bit(...)` toda vez).

```python
28 # Modos do letreiro (campo "mode" do payload Marquee — ver SPECS.md 4.2).
29 # Payload sem "mode" cai em MODE_SCROLL, que é o comportamento original.
30 MODE_SCROLL = "scroll"   # texto único rolando nas 4 linhas
31 MODE_LINES = "lines"     # 4 campos fixos, um por linha do display
32 MODE_BIG = "big"         # um caractere por vez, ampliado nas 4 linhas
33 _MODES = (MODE_SCROLL, MODE_LINES, MODE_BIG)
34
35 _WEEKDAYS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom")
36
37 # Diferença, em segundos, entre a época Unix (1970-01-01) e a época usada
38 # pelo MicroPython no ESP32 (2000-01-01).
39 _UNIX_TO_MPY_EPOCH_OFFSET = 946684800
40
41 # Epoch mínimo aceito (2020-01-01): protege o RTC de um payload absurdo.
42 _MIN_VALID_EPOCH = 1577836800
```

Constantes de configuração da aplicação: os 3 modos possíveis do
letreiro (usando o texto exato que trafega no JSON, ver `SPECS.md`),
nomes abreviados dos dias da semana, e a conversão de "época" — sistemas
diferentes contam o tempo a partir de datas diferentes ("época zero"): o
padrão do mundo (Unix, usado pelo Android) é 1970; o MicroPython no
ESP32 usa 2000. `946684800` é quantos segundos existem entre essas duas
datas — subtrair esse número converte um "epoch Unix" pro formato que o
RTC do ESP32 entende.

```python
44 _LOOP_SLEEP_MS = 20        # granularidade do laço: BLE responde em ~20ms
45 _TEMP_REFRESH_MS = 5000
46 _STATUS_REFRESH_MS = 5000
47 _SENSOR_RESCAN_MS = 30000  # tenta redetectar um sensor ligado depois
48 _MIN_SPEED_MS = 50         # ms por passo (1 coluna do display), em qualquer modo
49 _MAX_DURATION_S = 3600
50 _BIG_SCALE = 2
```

Todos os "ritmos" e limites da aplicação, num único lugar fácil de
ajustar: a cada 20ms o laço principal roda de novo (rápido o bastante
pra não deixar o Bluetooth "engasgar"); a cada 5 segundos, atualiza
temperatura e reenvia status; a cada 30s, tenta redetectar um sensor
que porventura tenha sido ligado depois do boot; velocidade mínima do
letreiro (50ms por coluna, senão fica rápido demais pra ler); duração
máxima de 1 hora; e a escala do letreiro ampliado (2x o tamanho normal).

```python
57 def _as_int(value, default):
58     try:
59         return int(value)
60     except (TypeError, ValueError):
61         return default
```

Função auxiliar: tenta converter qualquer coisa (`value`) pra número
inteiro; se não der certo (por exemplo, alguém mandou texto onde
deveria ser número), devolve um valor padrão em vez de travar. Isso
protege o firmware contra um app mal-comportado (ou um payload BLE
manual, digitado errado num app genérico) que mande, por exemplo,
`"duration_s": "trinta"` em vez de `30`.

```python
64 def _sanitize(text):
65     """Troca por '?' tudo que o HD44780 não sabe desenhar. O app Android já
66     remove acentos antes de enviar; isto é a rede de segurança para quem
67     escrever direto por um app BLE genérico (nRF Connect, etc.)."""
68     out = []
69     for ch in text:
70         out.append(ch if 0x20 <= ord(ch) <= 0x7D else "?")
71     return "".join(out)
```

Percorre cada caractere do texto recebido; se o código dele
(`ord(ch)`) estiver fora da faixa de caracteres imprimíveis normais
(0x20 a 0x7D — do espaço até o `}`), substitui por `"?"`. Isso evita que
um acento, emoji, ou qualquer coisa fora do alfabeto do HD44780 vire um
símbolo aleatório ilegível na tela.

```python
74 _SAKAMOTO = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
75
76
77 def _weekday_name(year, month, day):
78     if month < 1 or month > 12:
79         return "---"
80     y = year - 1 if month < 3 else year
81     weekday_sun0 = (y + y // 4 - y // 100 + y // 400 + _SAKAMOTO[month - 1] + day) % 7
82     return _WEEKDAYS[(weekday_sun0 + 6) % 7]
```

O **algoritmo de Sakamoto** — uma fórmula matemática clássica e compacta
pra calcular o dia da semana de qualquer data do calendário (sem
precisar de bibliotecas de data/hora completas, que MicroPython não
tem). `y // 4` é divisão inteira (descarta a parte decimal) — junto com
`// 100` e `// 400`, é a correção de anos bissextos do calendário
gregoriano. `% 7` pega o resto da divisão por 7, resultando num número
de 0 a 6 representando o dia da semana; a última linha ajusta esse
número pra bater com a nossa lista `_WEEKDAYS` (que começa em segunda,
não domingo). Esse cálculo é feito por conta própria em vez de usar o
campo "dia da semana" que o próprio RTC devolve, porque essa convenção
varia entre versões do MicroPython (documentado no comentário do código
de verdade).

### A classe `ClockApp`

```python
90 class ClockApp:
91     def __init__(self):
92         print("=== ", VERSION, " ===")
93
94         self._rtc = RTC()
95         self._lcd = LCD4Bit(
96             rs_pin=config.LCD_RS,
...
104        )
105        self._lcd.create_char(bigfont.BLOCK_INDEX, bigfont.BLOCK_BITMAP)
```

Cria o objeto do RTC, cria o objeto do display (passando os pinos
definidos em `config.py`), e grava o "bloco cheio" na CGRAM do display
logo no início — antes de qualquer letreiro ampliado ser exibido pela
primeira vez.

```python
111        self._sensor, sensor_version = self._init_sensor()
112        print("Modulos carregados:", config.VERSION, "|", lcd_hd44780.VERSION,
113              "|", ble_service.VERSION, "|", storage.VERSION,
114              "|", bigfont.VERSION, "|", sensor_version)
```

Tenta inicializar o sensor de temperatura (função explicada abaixo) e
imprime no Shell do Thonny a versão de **todos** os módulos carregados
— essa é a linha que você confere pra ter certeza de qual código está
realmente rodando no ESP32.

```python
116        self._temp_unit = storage.load_temp_unit()
117        self._last_temp_c = None
118        self._last_temp_ticks = ticks_ms()
119        self._last_scan_ticks = ticks_ms()
120        self._last_status_ticks = ticks_ms()
121        self._last_second = None
```

Carrega a unidade de temperatura salva (ou `"C"` por padrão, se nunca
foi configurada) e inicializa variáveis de controle de tempo (quando foi
a última leitura de temperatura, a última tentativa de redetectar o
sensor, o último envio de status) e `_last_second`, usada mais abaixo
pra saber quando o relógio precisa redesenhar a tela.

```python
131        self._show_mode = None
132        self._show_start = 0
133        self._show_duration_ms = 0
134        self._show_speed_ms = 300
135        self._show_last_step = 0
136        self._row_texts = [""] * config.LCD_ROWS
137        self._row_lengths = [0] * config.LCD_ROWS
138        self._row_offsets = [0] * config.LCD_ROWS
```

O estado do **Modo Letreiro**. `_show_mode = None` significa "Modo
Normal" (relógio funcionando normalmente); qualquer outro valor
(`"scroll"`, `"lines"`, `"big"`) significa que um letreiro está ativo.
`_row_texts`/`_row_lengths`/`_row_offsets` são 3 listas paralelas — uma
posição por linha do display — guardando, respectivamente: o texto (ou
tira de pixels) que está rolando naquela linha; o tamanho total dele; e
até onde já rolou. Essa estrutura é o que permite os 3 modos de letreiro
usarem **a mesma** função de desenho (`_render_show`, mais abaixo).

```python
140        self._ble = ClockBLEService(name="Relogio-ESP32")
141        self._ble.on_set_datetime = self._handle_set_datetime
142        self._ble.on_marquee = self._handle_marquee
143        self._ble.on_config_write = self._handle_config_write
144        self._ble.set_config({"temp_unit": self._temp_unit})
```

Cria o serviço Bluetooth e **conecta os callbacks**: diz explicitamente
"quando chegar uma escrita de SetDateTime, chame esta função aqui"
(`self._handle_set_datetime`, uma função desta própria classe, definida
mais abaixo) — é assim que `ble_service.py` (que não sabe nada sobre
relógio, display ou temperatura) consegue disparar comportamento
específico da aplicação sem os dois arquivos precisarem conhecer os
detalhes um do outro. Por fim, publica a unidade de temperatura atual na
característica Config, pra um app que acabou de conectar já poder ler
sem precisar mandar nada primeiro.

```python
146    def _init_sensor(self):
147        try:
148            import ds18b20_sensor
149            sensor = ds18b20_sensor.DS18B20(config.ONEWIRE_DATA)
150        except Exception as e:
151            print("Sensor de temperatura indisponivel:", e)
152            return None, "sem ds18b20_sensor"
153        if not sensor.available:
154            print("Nenhum DS18B20 no barramento - relogio segue sem temperatura.")
154        return sensor, ds18b20_sensor.VERSION
```

Repare que `import ds18b20_sensor` está **dentro** da função, não lá no
topo do arquivo — isso é proposital: se esse arquivo não estiver
gravado no ESP32 (por exemplo, alguém removeu por engano), ou se criar o
sensor falhar por qualquer motivo de hardware, o `try/except` evita que
o relógio inteiro deixe de funcionar por causa só da temperatura — ele
sobe sem sensor, mostrando um aviso na tela (função `_temp_text`,
abaixo), em vez de travar.

```python
159    def run(self):
160        while True:
161            try:
162                self._loop_once()
163            except Exception as e:
164                print("Erro no laco principal:", e)
165                sleep_ms(500)
```

O **laço infinito** do programa — `while True` roda pra sempre, é isso
que mantém o relógio "vivo" indefinidamente. Cada volta chama
`_loop_once()` protegida por `try/except`: se qualquer coisa inesperada
der erro numa volta específica do laço, o programa **não trava** — só
imprime o erro, espera meio segundo, e continua rodando a próxima volta
normalmente. Essa é a diferença entre um bug travar o relógio pra
sempre (precisando de reset manual) ou só causar um soluço passageiro.

```python
169    def _loop_once(self):
170        self._ble.tick()
171        self._service_temperature()
172        if self._show_mode is None:
173            self._render_clock()
174        else:
175            self._render_show()
176        self._service_status()
177        sleep_ms(_LOOP_SLEEP_MS)
```

Uma "volta" completa do relógio, em ordem: processa qualquer mensagem
Bluetooth pendente; atualiza a máquina de estados da temperatura;
desenha o relógio normal **ou** o letreiro (dependendo do modo atual);
atualiza o status Bluetooth se for a hora; espera 20ms antes da próxima
volta (dá uma folga pro processador, sem deixar o sistema "travado" —
um `while True` sem nenhuma pausa consumiria 100% do processador à
toa).

```python
181    def _service_temperature(self):
182        sensor = self._sensor
183        if sensor is None:
184            return
185        now = ticks_ms()
186
187        if sensor.result_ready():
188            value = sensor.read_result()
189            if value is not None:
190                self._last_temp_c = value
191            self._last_temp_ticks = now
192            return
193
194        if sensor.conversion_pending:
195            return
196
197        if not sensor.available:
198            if ticks_diff(now, self._last_scan_ticks) >= _SENSOR_RESCAN_MS:
199                self._last_scan_ticks = now
200                sensor.rescan()
201            return
202
203        if ticks_diff(now, self._last_temp_ticks) >= _TEMP_REFRESH_MS:
204            sensor.start_conversion()
```

Uma **máquina de estados** — a cada volta do laço, decide o que fazer
com o sensor de temperatura dependendo da situação atual, sem nunca
bloquear:
1. Sem sensor algum (183-184): não faz nada.
2. Uma conversão terminou (187-192): lê o resultado e guarda.
3. Uma conversão está em andamento, mas ainda não terminou (194-195):
   não faz nada ainda, só espera (volta aqui de novo na próxima volta do
   laço, 20ms depois).
4. Não há sensor detectado no barramento (197-201): a cada 30 segundos,
   tenta procurar de novo (por exemplo, se você ligou o sensor depois de
   o relógio já estar ligado).
5. Nenhuma das situações acima, e já passou tempo suficiente desde a
   última leitura (203-204): dispara uma nova conversão (sem esperar
   ela terminar — o resultado só vai ser lido numa volta futura, quando
   `result_ready()` finalmente disser que sim).

```python
206    def _temp_text(self):
207        if self._last_temp_c is None:
208            if self._sensor is None or not self._sensor.available:
209                return "Sem sensor de temp."
210            return "Temp: --"
211        if self._temp_unit == "F":
212            return "Temp: {:.1f} F".format(self._last_temp_c * 9 / 5 + 32)
212        return "Temp: {:.1f} C".format(self._last_temp_c)
```

Monta o texto da linha de temperatura do Modo Normal. Se nunca leu nada
ainda: mostra "Sem sensor" (se realmente não há sensor) ou "Temp: --"
(se há sensor, mas a primeira leitura ainda não terminou). Se já tem
uma leitura, converte pra Fahrenheit se for o caso (`°F = °C × 9/5 +
32`, a fórmula de conversão padrão) e formata com 1 casa decimal
(`{:.1f}` é a sintaxe de formatação do Python: 1 dígito depois da
vírgula).

```python
217    def _render_clock(self):
218        year, month, day, _wd, hour, minute, second, _sub = self._rtc.datetime()
219        if second == self._last_second:
220            return
220        self._last_second = second
...
225        self._lcd.write_line("{}, {:02d}/{:02d}/{:04d}".format(
226            _weekday_name(year, month, day), day, month, year), row=0)
227        self._lcd.write_line("{:02d}:{:02d}:{:02d}".format(hour, minute, second), row=1)
228        self._lcd.write_line(self._temp_text(), row=2)
229        self._lcd.write_line("Relogio ESP32 BLE", row=3)
```

Desenha o Modo Normal. `self._rtc.datetime()` devolve 8 valores de uma
vez (ano, mês, dia, dia da semana do RTC — ignorado, `_wd` —, hora,
minuto, segundo, e um sub-segundo — também ignorado, `_sub`).
**219-220**: se o segundo não mudou desde a última vez, não faz nada —
evita reprocessar tudo isso várias vezes por segundo à toa (o laço roda
a cada 20ms, ou seja, umas 50 vezes por segundo). `{:02d}` formata um
número sempre com 2 dígitos, completando com zero à esquerda se
necessário (`5` vira `"05"`) — assim a hora sempre aparece como `08:03:05`
em vez de `8:3:5`. Repare que, mesmo escrevendo as 4 linhas toda vez que
o segundo muda, o cache dentro de `write_line` (explicado lá em
`lcd_hd44780.py`) garante que só a linha que realmente mudou de conteúdo
vai efetivamente ao barramento do display.

```python
231    def _render_show(self):
232        now = ticks_ms()
233        if ticks_diff(now, self._show_start) >= self._show_duration_ms:
234            self._stop_show()
235            print("Modo Letreiro expirado, voltando ao Modo Normal")
236            return
237
238        if ticks_diff(now, self._show_last_step) < self._show_speed_ms:
239            return
240        self._show_last_step = now
241
242        cols = config.LCD_COLS
243        for row in range(config.LCD_ROWS):
244            text = self._row_texts[row]
245            length = self._row_lengths[row]
246            offset = self._row_offsets[row]
247            window = text[offset:offset + cols]
248            if len(window) < cols:
249                window += text[: cols - len(window)]
250            self._lcd.write_line(window, row)
251            self._row_offsets[row] = (offset + 1) % length
```

O coração visual do Modo Letreiro — a **mesma** função desenha os 3
modos (Rolagem, 4 Linhas, Ampliado), porque todos eles já foram
convertidos, na hora de configurar (função `_handle_marquee`, abaixo),
pro mesmo formato: até 4 "fitas" de texto/pixels.
- **233-236**: se já passou da duração configurada, encerra o letreiro e
  volta pro Modo Normal.
- **238-240**: controla a **velocidade** — só avança um passo se já
  passou tempo suficiente desde o último (senão sairia rolando rápido
  demais, numa velocidade ligada à do laço principal, 20ms, em vez da
  velocidade configurada pelo usuário).
- **242-251**: para cada linha do display, recorta uma "janela" de 20
  caracteres (`cols`) a partir da posição atual de rolagem
  (`offset`) — isso é o que faz o texto **parecer** deslizar da direita
  pra esquerda: a cada passo, o `offset` avança 1, então a janela
  "olha" pra um pedacinho mais à frente da fita.
  - **248-249**: se a janela recortada ficou menor que 20 caracteres
    (porque chegou perto do fim da fita), completa "dando a volta" —
    pega o começo da mesma fita de novo (`text[: cols - len(window)]`)
    — é assim que a fita se torna um **laço contínuo**, repetindo pra
    sempre enquanto o letreiro estiver ativo.
  - **251**: avança o offset em 1, e `% length` ("resto da divisão")
    garante que ele "dá a volta" de volta pro 0 quando chega no fim da
    fita, em vez de crescer pra sempre.

```python
253    def _stop_show(self):
254        self._show_mode = None
255        self._last_second = None  # força redesenho do relógio
256        self._push_status()
```

Encerra o letreiro: volta `_show_mode` pra `None` (Modo Normal). Zera
`_last_second` — truque pra garantir que, na próxima volta do laço,
`_render_clock` sempre redesenhe (linha 219 vai comparar o segundo atual
com `None`, que nunca é igual, então não vai pular o redesenho mesmo que
o segundo do relógio não tenha mudado desde a última vez que o Modo
Normal rodou). Por fim, avisa o app (via Bluetooth) que o modo mudou.

```python
260    def _service_status(self):
261        if ticks_diff(ticks_ms(), self._last_status_ticks) >= _STATUS_REFRESH_MS:
262            self._push_status()
263
264    def _push_status(self):
265        self._last_status_ticks = ticks_ms()
266        status = {
267            "mode": "normal" if self._show_mode is None else "marquee",
268            "connected": self._ble.is_connected(),
269        }
270        if self._show_mode is not None:
271            status["marquee_mode"] = self._show_mode
272        if self._last_temp_c is not None:
273            status["temp_c"] = round(self._last_temp_c, 1)
274        self._ble.set_status(status)
```

`_service_status` só chama `_push_status` a cada 5 segundos
(`_STATUS_REFRESH_MS`), pra não ficar mandando notificações Bluetooth o
tempo todo à toa. `_push_status` monta um **dicionário Python** com o
estado atual (modo, se está conectado, qual sub-modo de letreiro se
houver, e a temperatura arredondada pra 1 casa decimal se disponível) e
manda pro `ble_service` publicar — que converte isso em JSON e notifica
o app (ver `set_status` em `ble_service.py`).

```python
278    def _handle_set_datetime(self, data):
279        unix_epoch = _as_int(data.get("epoch"), None)
280        if unix_epoch is None or unix_epoch < _MIN_VALID_EPOCH:
281            print("Epoch invalido ignorado:", data.get("epoch"))
282            return
283        year, month, day, hour, minute, second, wday0, _yday = localtime(
284            unix_epoch - _UNIX_TO_MPY_EPOCH_OFFSET)
285        self._rtc.datetime((year, month, day, wday0 + 1, hour, minute, second, 0))
286        self._last_second = None
287        print("SetDateTime recebido, RTC ajustado:", self._rtc.datetime())
```

Chamada automaticamente (via o callback ligado lá no `__init__`, linha
141) sempre que o app manda um novo horário. `data.get("epoch")` lê o
campo `"epoch"` do JSON recebido (`.get` não dá erro se a chave não
existir, só devolve `None`). Se o valor não for um número válido, ou for
absurdamente antigo (antes de 2020), **ignora** — proteção contra um
payload malformado ou malicioso bagunçar o relógio. `localtime(...)`
converte o número de segundos (já ajustado pela diferença de época, linha
284) numa data/hora completa; `self._rtc.datetime((...))` grava isso de
volta no RTC de verdade do ESP32. `+1` no dia da semana (linha 285)
ajusta a convenção (`localtime` devolve 0=segunda, o RTC do ESP32 espera
1=segunda).

```python
289    def _handle_marquee(self, data):
290        mode = data.get("mode", MODE_SCROLL)
291        if mode not in _MODES:
292            mode = MODE_SCROLL
293
294        duration_s = _as_int(data.get("duration_s"), 30)
295        speed_ms = _as_int(data.get("speed_ms"), 300)
296
297        if mode == MODE_LINES:
298            content = self._prepare_lines(data)
299        else:
300            content = _sanitize(data.get("text", "")
301                                if isinstance(data.get("text"), str) else "")
302
303        if not content or duration_s <= 0:
304            if self._show_mode is not None:
305                self._stop_show()
306            print("Letreiro cancelado pelo app.")
307            return
```

Chamada quando o app manda uma mensagem de letreiro.
- **290-292**: lê o modo pedido; se vier vazio ou algo desconhecido, usa
  `scroll` como padrão (compatibilidade com payloads antigos, que nem
  tinham o campo `"mode"`).
- **297-301**: monta o "conteúdo" de forma diferente dependendo do modo —
  para `lines`, são as 4 linhas separadas (função `_prepare_lines`,
  abaixo); para os outros dois, é um texto único, passado por
  `_sanitize` (a função que troca caracteres não suportados por `?`).
  `isinstance(x, str)` checa se algo realmente é uma string de texto
  antes de tentar sanitizar — proteção contra o app mandar, por exemplo,
  um número onde deveria ser texto.
- **303-307**: se não sobrou conteúdo nenhum (texto vazio, ou as 4
  linhas todas vazias) **ou** a duração pedida é zero/negativa, isso é
  interpretado como um **pedido de cancelamento** — para o letreiro
  atual (se houver) e volta ao Modo Normal.

```python
310        duration_s = min(duration_s, _MAX_DURATION_S)
311        speed_ms = max(speed_ms, _MIN_SPEED_MS)
312        cols = config.LCD_COLS
313        pad = " " * cols
314
315        if mode == MODE_LINES:
316            row_texts = [pad + line + pad for line in content]
317        elif mode == MODE_BIG:
318            row_texts = [pad + strip + pad
319                        for strip in bigfont.render_strip(content, scale=_BIG_SCALE)]
320        else:
321            padded = pad + content + pad
322            row_texts = [padded] * config.LCD_ROWS
323
324        self._row_texts = row_texts
325        self._row_lengths = [len(t) for t in row_texts]
326        self._row_offsets = [0] * config.LCD_ROWS
```

- **310-311**: `min`/`max` aqui funcionam como **limites de segurança**:
  `min(duration_s, _MAX_DURATION_S)` garante que a duração nunca passe
  de 1 hora, não importa o que o app peça; `max(speed_ms,
  _MIN_SPEED_MS)` garante uma velocidade mínima (nunca mais rápido que
  50ms por passo).
- **313**: `pad` é um "colchão" de espaços em branco do tamanho de uma
  linha inteira.
- **315-322**: monta as "fitas" de cada linha, dependendo do modo — como
  já explicado na visão geral do estado (`_row_texts`, mais acima):
  - **316**: modo 4 Linhas — cada linha vira sua própria fita
    (`pad + line + pad`, ou seja, com espaço em branco em volta pra
    entrar/sair suavemente da tela).
  - **318-319**: modo Ampliado — pega as 4 tiras de pixels que
    `bigfont.render_strip` gera pro texto inteiro, e coloca o mesmo
    colchão de espaço em volta de cada uma.
  - **321-322**: modo Rolagem — uma única fita (o texto com espaço em
    volta), repetida 4 vezes (`[padded] * config.LCD_ROWS`), porque
    todas as linhas mostram o mesmo texto na mesma posição.
- **324-326**: guarda as fitas prontas, calcula o tamanho de cada uma, e
  reseta a posição de rolagem de todas as linhas pro início.

```python
328        self._show_mode = mode
329        self._show_speed_ms = speed_ms
330        self._show_duration_ms = duration_s * 1000
331        self._show_start = ticks_ms()
332        self._show_last_step = ticks_add(ticks_ms(), -speed_ms)
333        self._push_status()
334        print("Modo Letreiro ativado:", mode, "|", content,
335              "|", duration_s, "s @", speed_ms, "ms")
```

Ativa o letreiro de verdade: guarda o modo, velocidade e duração
(convertida de segundos pra milissegundos, linha 330, já que o resto do
código trabalha em milissegundos). `ticks_add(ticks_ms(), -speed_ms)`
"adianta" o relógio de controle de passo pra trás, garantindo que o
**primeiro** passo do letreiro apareça imediatamente (sem esperar
`speed_ms` antes do primeiro desenho) — usar `ticks_add` em vez de uma
subtração comum é necessário por causa do "estouro" natural do
`ticks_ms()` explicado lá em `ds18b20_sensor.py`. Por fim, avisa o app
via status e imprime um log no Shell.

```python
346    def _prepare_lines(self, data):
347        """Normaliza o campo "lines" para exatamente LCD_ROWS strings.
348        Devolve [] se todas vierem vazias (equivale a cancelar)."""
349        raw = data.get("lines")
350        if not isinstance(raw, list):
351            return []
352        lines = []
353        for row in range(config.LCD_ROWS):
354            value = raw[row] if row < len(raw) else ""
355            lines.append(_sanitize(value) if isinstance(value, str) else "")
356        return lines if any(line.strip() for line in lines) else []
```

Prepara o campo `"lines"` do JSON (uma lista de textos) pro formato
interno esperado — **sempre** exatamente 4 entradas, mesmo que o app
mande menos.
- **350-351**: se `"lines"` não for uma lista de verdade, trata como se
  não tivesse mandado nada.
- **353-355**: para cada uma das 4 linhas do display, pega o valor
  correspondente da lista recebida (`raw[row] if row < len(raw) else
  ""` — usa string vazia se o app mandou menos de 4 itens), e sanitiza
  se for texto (senão, também vira string vazia — proteção contra tipos
  errados).
- **356**: `any(line.strip() for line in lines)` verifica se **pelo
  menos uma** linha tem conteúdo de verdade (`.strip()` remove espaços
  em branco das pontas — uma linha só com espaços conta como vazia). Se
  todas as 4 estiverem realmente vazias, devolve lista vazia — que a
  função que chamou (`_handle_marquee`, linha 303) interpreta como
  pedido de cancelamento.

```python
358    def _handle_config_write(self, data):
359        unit = data.get("temp_unit")
360        if unit in ("C", "F"):
361            self._temp_unit = unit
362            storage.save_temp_unit(unit)
363            self._ble.set_config({"temp_unit": unit})
364            self._last_second = None  # força redesenho com a nova unidade
365        print("Config recebido:", data)
```

Chamada quando o app escreve na característica Config. Só aceita `"C"`
ou `"F"` como valores válidos; se for, atualiza a unidade em memória,
**grava na NVS** (sobrevive a reinícios — aqui é seguro chamar
`storage.save_temp_unit`, porque esta função roda a partir de
`tick()`/laço principal, nunca de dentro de uma IRQ — ver a "regra de
ouro" no topo de `ble_service.py`), confirma o novo valor de volta pro
app, e força redesenho da tela (pra atualizar a linha de temperatura
imediatamente, sem esperar o próximo segundo).

```python
370 def run():
371     ClockApp().run()
```

Função de conveniência no nível do módulo (fora da classe): cria uma
instância de `ClockApp` e imediatamente chama seu método `.run()`
(o laço infinito). É esta função que `main.py` chama.

---

## 8. `main.py` — o ponto de entrada

```python
12 import clock_app
13
14 clock_app.run()
```

O arquivo mais curto de todos, e o único cujo **nome importa**: o
MicroPython, ao ligar, procura automaticamente por um arquivo chamado
exatamente `main.py` na raiz do sistema de arquivos e o executa sozinho
— é assim que o relógio funciona "plugado na tomada", sem precisar do
Thonny nem de um computador por perto. Todo o resto do arquivo (linhas
1-11) é só comentário explicando esse comportamento; o código de
verdade são só essas 2 linhas, que entregam o controle pra
`clock_app.run()` — e a partir daí, o programa nunca mais "volta" pra
cá; fica rodando o `while True` de `ClockApp.run()` para sempre (ou até
a energia cair).

---

## Resumo do fluxo completo

1. ESP32 liga → MicroPython roda `main.py` → chama `clock_app.run()`.
2. `ClockApp()` é criado: monta o display, tenta achar o sensor de
   temperatura, carrega a unidade salva na NVS, sobe o serviço
   Bluetooth e começa a anunciar como `"Relogio-ESP32"`.
3. `.run()` entra num laço infinito, chamando `_loop_once()` a cada
   20ms, pra sempre.
4. Cada volta do laço: processa mensagens Bluetooth pendentes,
   avança a máquina de estados da temperatura, desenha a tela (relógio
   normal ou letreiro), e a cada 5s reenvia o status pro app.
5. Quando o app manda uma mensagem (ajustar hora, ativar letreiro,
   trocar unidade), o `ble_service.py` remonta os fragmentos, valida o
   JSON, e chama de volta uma função específica do `clock_app.py` — que
   é quem realmente decide o que fazer com aquela informação.
