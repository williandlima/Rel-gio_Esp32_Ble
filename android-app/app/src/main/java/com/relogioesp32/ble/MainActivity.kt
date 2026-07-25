package com.relogioesp32.ble

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
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
        ble.onStatusChanged = { json -> runOnUiThread { binding.textStatus.text = json } }
        ble.onConfigRead = { json -> runOnUiThread { showConfig(json) } }

        setDisconnectedState()

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
            binding.textSyncStatus.setTextColor(getColor(R.color.text_success))
        }

        binding.buttonSendMarquee.setOnClickListener {
            val text = binding.editMarqueeText.text.toString()
            if (text.isBlank()) {
                binding.textMarqueeError.visibility = View.VISIBLE
                return@setOnClickListener
            }
            binding.textMarqueeError.visibility = View.GONE
            val duration = binding.editMarqueeDuration.text.toString().toIntOrNull() ?: 30
            val speed = binding.editMarqueeSpeed.text.toString().toIntOrNull() ?: 300
            ble.writeMarquee(text, duration, speed)
        }

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

    // O botao de topo e o selo de status tem 3 estados, igual a maioria dos
    // apps de BLE (nRF Connect, etc.): navy = desconectado (pronto pra
    // conectar), cinza = conectando, taupe/verde = conectado. Enquanto nao
    // estiver tudo pronto, as demais acoes ficam desabilitadas.
    private fun setDisconnectedState() {
        isConnected = false
        binding.buttonConnect.setText(R.string.button_connect)
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_navy)
        binding.buttonConnect.setTextColor(getColor(R.color.primary_navy_text))
        binding.textConnectionBadge.setText(R.string.badge_disconnected)
        binding.textConnectionBadge.setBackgroundResource(R.drawable.bg_status_pill_disconnected)
        binding.textConnectionBadge.setTextColor(getColor(R.color.text_label))
        setBleControlsEnabled(false)
    }

    private fun setConnectingState() {
        // Continua clicavel: se o ESP32 nunca aparecer, o usuario nao fica
        // preso (e o scan tem timeout proprio no BleManager).
        binding.buttonConnect.setText(R.string.button_connecting)
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_muted)
        binding.buttonConnect.setTextColor(getColor(R.color.muted_text))
        binding.textConnectionBadge.setText(R.string.badge_connecting)
        binding.textConnectionBadge.setBackgroundResource(R.drawable.bg_status_pill_muted)
        binding.textConnectionBadge.setTextColor(getColor(R.color.muted_text))
    }

    private fun setConnectedState() {
        isConnected = true
        binding.buttonConnect.setText(R.string.button_disconnect)
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_taupe)
        binding.buttonConnect.setTextColor(getColor(R.color.taupe_text))
        binding.textConnectionBadge.setText(R.string.badge_connected)
        binding.textConnectionBadge.setBackgroundResource(R.drawable.bg_status_pill_connected)
        binding.textConnectionBadge.setTextColor(getColor(R.color.text_success))
        // Os controles só liberam em onReady (serviços descobertos).
    }

    private fun setBleControlsEnabled(enabled: Boolean) {
        val alpha = if (enabled) 1f else 0.45f
        listOf(
            binding.buttonSyncTime,
            binding.buttonSendMarquee,
            binding.buttonSaveConfig,
            binding.buttonReadConfig,
            binding.radioCelsius,
            binding.radioFahrenheit
        ).forEach {
            it.isEnabled = enabled
            it.alpha = alpha
        }
    }

    override fun onDestroy() {
        ble.release()
        super.onDestroy()
    }
}
