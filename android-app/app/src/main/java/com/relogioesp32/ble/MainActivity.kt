package com.relogioesp32.ble

import android.Manifest
import android.bluetooth.BluetoothAdapter
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
            appendLog("Permissoes negadas - nao e possivel usar Bluetooth.")
            setDisconnectedState()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val versionName = packageManager.getPackageInfo(packageName, 0).versionName
        appendLog("App versao: $versionName")

        ble = BleManager(applicationContext)
        ble.onLog = { msg -> runOnUiThread { appendLog(msg) } }
        ble.onConnectionStateChange = { connected ->
            runOnUiThread {
                if (connected) setConnectedState() else setDisconnectedState()
            }
        }
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
            val localEpochSeconds = (nowUtcMillis + offsetMillis) / 1000
            ble.writeSetDateTime(localEpochSeconds)

            val now = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
            binding.textSyncStatus.text = "Sincronizado as $now"
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
        }

        binding.buttonReadConfig.setOnClickListener { ble.readConfig() }

        binding.textConfigJsonLink.setOnClickListener {
            jsonVisible = !jsonVisible
            binding.textConfig.visibility = if (jsonVisible) View.VISIBLE else View.GONE
            binding.textConfigJsonLink.text = if (jsonVisible) "Ocultar JSON" else "Ver JSON"
        }
    }

    private fun showConfig(json: String) {
        binding.textConfig.text = json
        val unit = try {
            JSONObject(json).optString("temp_unit", "-")
        } catch (e: Exception) {
            "-"
        }
        val friendlyUnit = when (unit) {
            "F" -> "Fahrenheit"
            "C" -> "Celsius"
            else -> "-"
        }
        binding.textConfigSummary.text = "Unidade salva no relogio: $friendlyUnit"
    }

    private fun requestPermissionsAndScan() {
        val adapter = BluetoothAdapter.getDefaultAdapter()
        if (adapter == null || !adapter.isEnabled) {
            appendLog("Ative o Bluetooth do celular primeiro.")
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

    // O botao de topo tem 3 estados visuais, igual a maioria dos apps de
    // BLE (nRF Connect, etc.): navy = desconectado (pronto pra conectar),
    // cinza/muted = conectando (aguardando o ESP32 responder), taupe =
    // conectado (pronto pra desconectar). Enquanto nao conectado, as
    // demais acoes ficam desabilitadas para nao gerar escritas BLE sem
    // efeito nenhum.
    private fun setDisconnectedState() {
        isConnected = false
        binding.buttonConnect.isEnabled = true
        binding.buttonConnect.text = "Conectar ao Relogio-ESP32"
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_navy)
        binding.buttonConnect.setTextColor(getColor(R.color.primary_navy_text))
        setBleControlsEnabled(false)
    }

    private fun setConnectingState() {
        // Fica clicavel (nao trava o usuario caso o ESP32 nunca seja
        // encontrado) - tocar de novo so reforca a mesma tentativa de scan.
        binding.buttonConnect.text = "Conectando..."
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_muted)
        binding.buttonConnect.setTextColor(getColor(R.color.muted_text))
    }

    private fun setConnectedState() {
        isConnected = true
        binding.buttonConnect.isEnabled = true
        binding.buttonConnect.text = "Desconectar"
        binding.buttonConnect.setBackgroundResource(R.drawable.bg_button_taupe)
        binding.buttonConnect.setTextColor(getColor(R.color.taupe_text))
        setBleControlsEnabled(true)
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
        ble.disconnect()
        super.onDestroy()
    }
}
