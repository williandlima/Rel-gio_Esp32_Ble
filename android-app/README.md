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
2. Toque em **"Conectar ao Relogio-ESP32"** — conceda as permissões de
   Bluetooth/Localização pedidas.
3. Quando conectar, o texto de status muda para "Conectado" e o app
   assina as notificações de **Status** automaticamente (deve começar a
   aparecer `{"mode": "normal", "temp_c": ..., "connected": true}` a cada
   ~5s).
4. Toque em **"Sincronizar hora com o celular"** — a hora do display do
   relógio deve mudar para a hora atual (já ajustada pro fuso horário
   local do celular, ao contrário do teste manual anterior via nRF Connect
   que usava UTC puro).
5. Preencha o texto/duração/velocidade do letreiro e toque em **"Enviar
   letreiro"** — por enquanto só aparece no Shell do Thonny (`Marquee
   recebido: {...}`), o comportamento real no display é a etapa 5 do
   roadmap.
6. Teste **"Salvar configuracao"** (Celsius/Fahrenheit) e **"Ler
   configuracao atual"**.

## Estrutura

```
app/src/main/
  AndroidManifest.xml
  java/com/relogioesp32/ble/
    MainActivity.kt      Tela única, permissões e callbacks de UI
    BleManager.kt         Cliente BLE (scan, connect, GATT read/write/notify)
  res/layout/
    activity_main.xml     Layout da tela única
```
