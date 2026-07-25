# App Android — Relogio_Esp32_Ble

App Kotlin simples (sem bibliotecas externas — só APIs nativas de Bluetooth
Low Energy do Android) para configurar o relógio via BLE, seguindo o
protocolo definido no `SPECS.md` (seção 4) e implementado em
`firmware/ble_service.py`.

## Como abrir o projeto no Android Studio

Este diretório (`android-app/`) já é um projeto Gradle completo — build
files, manifest, ícone, layout, código Kotlin **e o Gradle Wrapper**
(`gradlew`, `gradlew.bat`, `gradle/wrapper/`). Não precisa usar o
assistente "New Project" nem gerar nada manualmente:

1. Abra o Android Studio → **Open** (não "New Project") → selecione a
   pasta `android-app/` deste repositório.
2. Aguarde a sincronização automática do Gradle (barra de progresso
   embaixo). Na primeira vez, o próprio `gradlew` baixa o Gradle 8.14.3 e
   as dependências do projeto — precisa de internet liberada para
   `services.gradle.org`, `dl.google.com`/`maven.google.com` (SDK e
   Android Gradle Plugin) e Maven Central (dependências do app).
3. Para gerar o APK sem precisar abrir a IDE inteira, use o terminal
   (pode ser o da própria IDE — **View → Tool Windows → Terminal** — ou
   um PowerShell/terminal comum):
   ```bash
   cd android-app
   ./gradlew assembleDebug        # Mac/Linux
   .\gradlew.bat assembleDebug    # Windows
   ```
   O instalável fica em `app/build/outputs/apk/debug/app-debug.apk` — é
   só copiar esse arquivo pro celular (cabo, WhatsApp, e-mail, Drive...)
   e tocar nele pra instalar (pode pedir pra habilitar "instalar de
   fontes desconhecidas" na primeira vez).

   **Erro comum**: `JAVA_HOME is not set and no 'java' command could be
   found in your PATH`. Acontece porque um terminal solto não tem a
   variável de ambiente que o Android Studio usa internamente — mas a
   IDE já vem com um Java embutido, então basta apontar pra ele nessa
   sessão do terminal antes de rodar o `gradlew`:
   ```powershell
   $env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"   # Windows
   export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"  # Mac
   ```
   (ajuste o caminho se o Android Studio estiver instalado em outro
   lugar). Depois disso, `./gradlew assembleDebug` funciona normalmente.

## Por que o build/APK não sai pronto deste repositório

Este ambiente remoto tem acesso à internet restrito por política: o
Gradle Wrapper foi gerado com sucesso aqui (havia um Gradle instalado
localmente e `services.gradle.org` está liberado), mas a compilação em si
depende do **Android Gradle Plugin** e do **Android SDK** (`android.jar`,
`aapt2`, etc.), hospedados em `dl.google.com` — esse host é bloqueado de
propósito pela política de rede deste ambiente (confirmado: a conexão é
recusada mesmo por um domínio alternativo, `maven.google.com`, que
redireciona para o mesmo host). Por isso o `.apk` final só pode ser
gerado numa máquina com internet normal — a sua.

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
