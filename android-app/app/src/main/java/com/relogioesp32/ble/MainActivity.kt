package com.relogioesp32.ble

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.EditText
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.relogioesp32.ble.databinding.ActivityMainBinding
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var ble: BleManager
    private var isConnected = false
    private var jsonVisible = false
    private var marqueeRunning = false

    private val requestPermissionsLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        if (results.values.all { it }) {
            ble.startScan()
        } else {
            appendLog(getString(R.string.log_permissions_denied))
            setDisconnectedState()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val versionName = packageManager.getPackageInfo(packageName, 0).versionName
        appendLog(getString(R.string.log_app_version, versionName))

        ble = BleManager(applicationContext)
        ble.onLog = { msg -> runOnUiThread { appendLog(msg) } }
        ble.onConnectionStateChange = { connected ->
            runOnUiThread {
                if (connected) setConnectedState() else setDisconnectedState()
            }
        }
        // Só depois da descoberta de serviços as características existem —
        // liberar os botões antes disso deixava o usuário tocar em algo que
        // falharia com "caracteristica nao encontrada".
        ble.onReady = { runOnUiThread { setBleControlsEnabled(true) } }
        ble.onScanTimeout = { runOnUiThread { setDisconnectedState() } }
        ble.onStatusChanged = { json -> runOnUiThread { showStatus(json) } }
        ble.onConfigRead = { json -> runOnUiThread { showConfig(json) } }

        setDisconnectedState()
        setMarqueeRunning(false)
        applyMarqueeMode()

        binding.buttonConnect.setOnClickListener {
            if (isConnected) {
                ble.disconnect()
            } else {
                setConnectingState()
                requestPermissionsAndScan()
            }
        }

        binding.buttonSyncTime.setOnClickListener {
            // O firmware nao faz conversao de fuso horario (ver SPECS.md
            // secao 2.3/4.2) - por isso enviamos o epoch ja deslocado pelo
            // fuso local, para o RTC do ESP32 exibir a hora certa da regiao.
            val nowUtcMillis = System.currentTimeMillis()
            val offsetMillis = TimeZone.getDefault().getOffset(nowUtcMillis)
            ble.writeSetDateTime((nowUtcMillis + offsetMillis) / 1000)

            val now = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
            binding.textSyncStatus.text = getString(R.string.sync_done, now)
            binding.textSyncStatus.setTextColor(getColor(R.color.state_on))
            // Acionado: o botão passa a verde para registrar que já rodou.
            binding.buttonSyncTime.setBackgroundResource(R.drawable.bg_button_outline_done)
            binding.buttonSyncTime.setTextColor(getColorStateList(R.color.text_on_outline_done))
        }

        binding.radioGroupMarqueeMode.setOnCheckedChangeListener { _, _ -> applyMarqueeMode() }

        binding.buttonSendMarquee.setOnClickListener { sendMarquee() }
        binding.buttonStopMarquee.setOnClickListener { ble.writeMarqueeStop() }

        binding.buttonSaveConfig.setOnClickListener {
            val unit = if (binding.radioFahrenheit.isChecked) "F" else "C"
            ble.writeConfig(unit)
            // Relê logo em seguida para o resumo mostrar o que o relógio de
            // fato gravou, e não apenas o que pedimos. A fila do BleManager
            // garante que a leitura só sai depois da escrita terminar.
            ble.readConfig()
        }

        binding.buttonReadConfig.setOnClickListener { ble.readConfig() }

        binding.textConfigJsonLink.setOnClickListener {
            jsonVisible = !jsonVisible
            binding.textConfig.visibility = if (jsonVisible) View.VISIBLE else View.GONE
            binding.textConfigJsonLink.setText(
                if (jsonVisible) R.string.link_hide_json else R.string.link_show_json
            )
        }
    }

    // ---- Letreiro ----

    /** Mostra apenas os campos que fazem sentido no modo escolhido. */
    private fun applyMarqueeMode() {
        val lines = binding.radioModeLines.isChecked
        val big = binding.radioModeBig.isChecked

        binding.editMarqueeText.visibility = if (lines) View.GONE else View.VISIBLE
        binding.groupMarqueeLines.visibility = if (lines) View.VISIBLE else View.GONE
        // No modo 4 linhas o conteúdo é estático: não há velocidade de passo.
        binding.editMarqueeSpeed.visibility = if (lines) View.GONE else View.VISIBLE
        binding.textMarqueeError.visibility = View.GONE

        binding.editMarqueeSpeed.setHint(
            if (big) R.string.hint_marquee_speed_big else R.string.hint_marquee_speed
        )
        binding.textMarqueeHelp.text = getString(
            when {
                lines -> R.string.marquee_help_lines
                big -> R.string.marquee_help_big
                else -> R.string.marquee_help_scroll
            }
        ) + " " + getString(R.string.marquee_help_accents)
    }

    private fun sendMarquee() {
        val duration = binding.editMarqueeDuration.text.toString().toIntOrNull() ?: 30
        val speed = binding.editMarqueeSpeed.text.toString().toIntOrNull() ?: 300

        if (binding.radioModeLines.isChecked) {
            val lines = lineFields().map { it.text.toString() }
            if (lines.all { it.isBlank() }) {
                showMarqueeError(R.string.error_lines_empty)
                return
            }
            binding.textMarqueeError.visibility = View.GONE
            ble.writeMarqueeLines(lines, duration)
            return
        }

        val text = binding.editMarqueeText.text.toString()
        if (text.isBlank()) {
            showMarqueeError(R.string.error_marquee_empty)
            return
        }
        binding.textMarqueeError.visibility = View.GONE

        if (binding.radioModeBig.isChecked) {
            ble.writeMarqueeBig(text, duration, speed)
        } else {
            ble.writeMarqueeScroll(text, duration, speed)
        }
    }

    private fun lineFields(): List<EditText> = listOf(
        binding.editLine1, binding.editLine2, binding.editLine3, binding.editLine4
    )

    private fun showMarqueeError(resId: Int) {
        binding.textMarqueeError.setText(resId)
        binding.textMarqueeError.visibility = View.VISIBLE
    }

    /** Verde enquanto o letreiro está no ar; cinza quando parado. O estado
     *  vem das notificações de Status, ou seja, do próprio relógio. */
    private fun setMarqueeRunning(running: Boolean) {
        marqueeRunning = running
        binding.textMarqueeState.setText(
            if (running) R.string.marquee_state_on else R.string.marquee_state_off
        )
        binding.textMarqueeState.setBackgroundResource(
            if (running) R.drawable.bg_status_pill_connected
            else R.drawable.bg_status_pill_disconnected
        )
        binding.textMarqueeState.setTextColor(
            getColor(if (running) R.color.state_on else R.color.state_off)
        )
        val canStop = running && isConnected
        binding.buttonStopMarquee.isEnabled = canStop
    }

    // ---- Leituras do relógio ----

    private fun showStatus(json: String) {
        binding.textStatus.text = json
        val mode = try {
            JSONObject(json).optString("mode", "")
        } catch (e: Exception) {
            ""
        }
        if (mode.isNotEmpty()) setMarqueeRunning(mode == "marquee")
    }

    private fun showConfig(json: String) {
        binding.textConfig.text = json
        val unit = try {
            JSONObject(json).optString("temp_unit", "")
        } catch (e: Exception) {
            ""
        }
        when (unit) {
            "F" -> binding.textConfigSummary.text =
                getString(R.string.config_summary, getString(R.string.unit_fahrenheit))
            "C" -> binding.textConfigSummary.text =
                getString(R.string.config_summary, getString(R.string.unit_celsius))
            else -> binding.textConfigSummary.setText(R.string.config_summary_unknown)
        }
        // Mantém o seletor coerente com o que está gravado no relógio.
        if (unit == "F") binding.radioFahrenheit.isChecked = true
        else if (unit == "C") binding.radioCelsius.isChecked = true
    }

    // ---- Conexão ----

    private fun requestPermissionsAndScan() {
        if (!ble.isBluetoothEnabled()) {
            appendLog(getString(R.string.log_enable_bluetooth))
            setDisconnectedState()
            return
        }

        val needed = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }

        val allGranted = needed.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }

        if (allGranted) {
            ble.startScan()
        } else {
            requestPermissionsLauncher.launch(needed)
        }
    }

    private fun appendLog(msg: String) {
        binding.textLog.append("\n$msg")
        binding.scrollLog.post { binding.scrollLog.fullScroll(View.FOCUS_DOWN) }
    }

    // O botao de topo e o selo de status seguem a mesma semantica de cor do
    // resto da tela: azul-marinho = acao disponivel, cinza = desligado ou
    // ocupado, verde = conectado/acionado.
    private fun setDisconnectedState() {
        isConnected = false
        binding.buttonConnect.setText(R.string.button_connect)
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_primary)
        binding.buttonConnect.setTextColor(getColor(R.color.primary_navy_text))
        binding.textConnectionBadge.setText(R.string.badge_disconnected)
        binding.textConnectionBadge.setBackgroundResource(R.drawable.bg_status_pill_disconnected)
        binding.textConnectionBadge.setTextColor(getColor(R.color.state_off))
        setBleControlsEnabled(false)
        setMarqueeRunning(false)
        resetSyncIndicator()
    }

    private fun setConnectingState() {
        // Continua clicavel: se o ESP32 nunca aparecer, o usuario nao fica
        // preso (e o scan tem timeout proprio no BleManager).
        binding.buttonConnect.setText(R.string.button_connecting)
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_muted)
        // Fundo claro nesse estado: texto branco ficaria ilegível.
        binding.buttonConnect.setTextColor(getColor(R.color.muted_text))
        binding.textConnectionBadge.setText(R.string.badge_connecting)
        binding.textConnectionBadge.setBackgroundResource(R.drawable.bg_status_pill_muted)
        binding.textConnectionBadge.setTextColor(getColor(R.color.muted_text))
    }

    private fun setConnectedState() {
        isConnected = true
        binding.buttonConnect.setText(R.string.button_disconnect)
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_success)
        binding.buttonConnect.setTextColor(getColor(R.color.state_on_text))
        binding.textConnectionBadge.setText(R.string.badge_connected)
        binding.textConnectionBadge.setBackgroundResource(R.drawable.bg_status_pill_connected)
        binding.textConnectionBadge.setTextColor(getColor(R.color.state_on))
        // Os controles só liberam em onReady (serviços descobertos).
    }

    private fun resetSyncIndicator() {
        binding.textSyncStatus.setText(R.string.sync_never)
        binding.textSyncStatus.setTextColor(getColor(R.color.state_off))
        binding.buttonSyncTime.setBackgroundResource(R.drawable.bg_button_outline)
        binding.buttonSyncTime.setTextColor(getColorStateList(R.color.text_on_outline))
    }

    /** Habilita/desabilita tudo que depende de conexão. A cor vem dos
     *  seletores de estado dos drawables, então não é preciso mexer em alpha. */
    private fun setBleControlsEnabled(enabled: Boolean) {
        listOf(
            binding.buttonSyncTime,
            binding.buttonSendMarquee,
            binding.buttonSaveConfig,
            binding.buttonReadConfig,
            binding.radioCelsius,
            binding.radioFahrenheit,
            binding.radioModeScroll,
            binding.radioModeLines,
            binding.radioModeBig,
            binding.editMarqueeText,
            binding.editMarqueeDuration,
            binding.editMarqueeSpeed,
            binding.editLine1,
            binding.editLine2,
            binding.editLine3,
            binding.editLine4
        ).forEach { it.isEnabled = enabled }
        // "Parar letreiro" só faz sentido se houver letreiro no ar.
        binding.buttonStopMarquee.isEnabled = enabled && marqueeRunning
    }

    override fun onDestroy() {
        ble.release()
        super.onDestroy()
    }
}
