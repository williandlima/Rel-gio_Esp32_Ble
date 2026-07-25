# App Android — Relogio_Esp32_Ble

App Kotlin simples (sem bibliotecas externas — só APIs nativas de Bluetooth
Low Energy do Android) para configurar o relógio via BLE, seguindo o
protocolo definido no `SPECS.md` (seção 4) e implementado em
`firmware/ble_service.py`.

## Como abrir o projeto no Android Studio

Este diretório (`android-app/`) já é um projeto Gradle completo (build
files, manifest, ícone, layout, código Kotlin) — **não precisa usar o
assistente "New Project"**. Só falta uma coisa que não deu pra gerar aqui
no ambiente remoto (rede bloqueada para os servidores da Google/Gradle):
o **Gradle Wrapper**. É rápido de resolver no seu Mac, que tem internet
normal:

1. Abra o Android Studio → **Open** (não "New Project") → selecione a
   pasta `android-app/` deste repositório.
2. O Android Studio deve avisar que falta o Gradle Wrapper (ou tentar
   sincronizar e falhar por isso). Se aparecer um aviso oferecendo para
   criar o wrapper automaticamente, aceite.
3. **Se não aparecer esse aviso automaticamente**, abra o terminal
   integrado do Android Studio (**View > Tool Windows > Terminal**) e
   rode:
   ```bash
   gradle wrapper --gradle-version 8.7 --distribution-type all
   ```
   (usa um Gradle instalado no seu Mac via Homebrew — `brew install
   gradle` — se o comando `gradle` não existir).
4. Depois disso, clique em **"Sync Project with Gradle Files"** (ícone do
   elefante com a setinha, na barra de ferramentas).

Com o wrapper criado uma vez, tudo funciona normalmente daqui pra frente —
inclusive para quem clonar o repositório depois de você (o wrapper vai
para o Git).

## Como testar

Pré-requisito: o ESP32 rodando `test_ble.py` (ou uma versão futura do
firmware com BLE ativo), anunciando como **"Relogio-ESP32"**.

1. Rode o app num celular Android físico (BLE não funciona bem em
   emulador) conectado via cabo USB, com depuração USB ativada.
2. Toque em **"Conectar ao Relogio-ESP32"** (azul-marinho) — conceda as
   permissões de Bluetooth/Localização pedidas. O botão muda pra
   **"Conectando…"** (cinza) enquanto procura o dispositivo. Se o relógio
   não aparecer em 15 s, o app desiste sozinho e avisa no log.
3. Quando conectar, o botão fica **"Desconectar"** (castanho/taupe) e o
   selo do topo fica verde. As demais ações só ficam clicáveis depois que
   os serviços BLE são descobertos — é por isso que elas podem levar um
   instante a mais para acender. O app assina as notificações de
   **Status** e lê a configuração atual automaticamente.
4. Toque em **"Sincronizar hora com o celular"** — a hora do display do
   relógio deve mudar para a hora atual (já ajustada pro fuso horário
   local do celular, ao contrário do teste manual anterior via nRF Connect
   que usava UTC puro).
5. Escolha o **modo do letreiro** no seletor de três segmentos e preencha
   os campos que aparecerem. Os três rolam da direita para a esquerda —
   entrando pela última coluna do display e saindo pela primeira — no
   mesmo ritmo configurado em "Velocidade (ms por passo)":
   - **Rolagem**: um texto só, as 4 linhas mostram o mesmo conteúdo.
   - **4 linhas**: um campo por linha do display, cada linha rolando de
     forma independente (podem ter tamanhos diferentes).
   - **Ampliado**: o texto em blocos gigantes ocupando as 4 linhas,
     deslizando pixel a pixel — como um letreiro de LED, sem trocar de
     letra inteira de uma vez.

   Toque em **"Enviar letreiro"** — o display muda na hora e volta sozinho
   ao Modo Normal quando a duração acabar; **"Parar letreiro"** interrompe
   antes disso. O selo ao lado do título fica verde enquanto há letreiro no
   ar (a informação vem das notificações do próprio relógio, não de um
   palpite do app). Acentos são removidos antes do envio ("ação" vira
   "acao"): o HD44780 não tem esses caracteres e mostraria símbolos
   aleatórios.
6. Teste **"Salvar configuração"** (Celsius/Fahrenheit) e **"Ler atual"** —
   o resumo ("Unidade salva no relógio: ...") atualiza, e o link **"Ver
   JSON"** mostra/esconde o payload bruto recebido.

## Notas de implementação

- **Fila de operações GATT**: o Android só aceita uma operação por vez
  (write/read/descritor). O `BleManager` serializa tudo numa fila que só
  avança no callback — sem isso, dois toques rápidos em botões diferentes
  intercalavam fragmentos e o firmware remontava lixo.
- **`gatt.close()`**: chamado em toda desconexão. Sem isso, cada ciclo
  conectar/desconectar vaza um registro de cliente GATT, e depois de
  algumas dezenas de ciclos o Android para de conectar sem dar erro.
- **Escritas fatiadas em 20 bytes**: a API clássica não fragmenta payloads
  maiores que o MTU — ela trunca e não reenvia o resto. O firmware remonta
  os pedaços (ver `firmware/ble_service.py`).
- **Semântica de cor**: verde = acionado/conectado (selo de conexão, botão
  quando conectado, segmento selecionado, letreiro no ar), cinza =
  desligado/desconectado/indisponível. Cada botão tem um seletor de estado
  próprio (`res/drawable/bg_button_*.xml`) cobrindo normal, pressionado e
  desabilitado — o estado desabilitado é uma cor de verdade, não
  transparência.
- **Proporções**: alturas, raios, margens e tamanhos de texto saem de
  `res/values/dimens.xml`. Ações de largura total têm 52dp; controles
  pareados e segmentos de seletor têm 48dp, com o raio ajustado a cada
  altura. Os botões de meia largura usam texto auto-dimensionável para não
  truncar rótulos longos.

## Estrutura

```
app/src/main/
  AndroidManifest.xml
  java/com/relogioesp32/ble/
    MainActivity.kt       Tela única, permissões e estados da UI
    BleManager.kt         Cliente BLE (scan, connect, fila de operações GATT)
  res/layout/
    activity_main.xml     Layout da tela única
  res/values/
    strings.xml           Todos os textos da interface
    colors.xml            Paleta do design
    themes.xml            Tema sem ActionBar, barra de status clara
```
