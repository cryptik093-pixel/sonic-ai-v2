"""
Minimal live Sonic AI engine.

Stage 1 pipeline:
    microphone capture -> anomaly detection -> pitch estimation -> MIDI output

The engine is designed to be import-safe in the web app. MIDI output is optional:
if `mido` is unavailable or no MIDI port can be opened, the engine will still run
in monitor mode and report note events through the status API.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import sounddevice as sd


@dataclass
class LiveConfig:
    sample_rate: int = 44100
    block_size: int = 2048
    energy_threshold: float = 0.02
    peak_threshold: float = 0.12
    pitch_min_hz: float = 60.0
    pitch_max_hz: float = 1400.0
    note_velocity: int = 92
    note_duration_sec: float = 0.35
    cooldown_sec: float = 0.2


class LiveSonicEngine:
    def __init__(self, config: Optional[LiveConfig] = None) -> None:
        self.config = config or LiveConfig()
        self.stream = None
        self.stream_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.running = False
        self.events_sent = 0
        self.last_event: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.last_trigger_time = 0.0
        self.midi_port = None
        self.midi_port_name: Optional[str] = None
        self.midi_enabled = False
        self._timers = []

    def status(self) -> Dict[str, Any]:
        with self.state_lock:
            return {
                "running": self.running,
                "sample_rate": self.config.sample_rate,
                "block_size": self.config.block_size,
                "energy_threshold": self.config.energy_threshold,
                "peak_threshold": self.config.peak_threshold,
                "midi_enabled": self.midi_enabled,
                "midi_port_name": self.midi_port_name,
                "events_sent": self.events_sent,
                "last_event": self.last_event,
                "last_error": self.last_error,
            }

    def start(self, midi_port_name: Optional[str] = None) -> Dict[str, Any]:
        with self.stream_lock:
            if self.running:
                return self.status()

            self.last_error = None
            self._setup_midi(midi_port_name)

            try:
                self.stream = sd.InputStream(
                    callback=self._audio_callback,
                    channels=1,
                    samplerate=self.config.sample_rate,
                    blocksize=self.config.block_size,
                )
                self.stream.start()
            except Exception as exc:
                self.running = False
                self.stream = None
                self.last_error = f"Audio input start failed: {exc}"
                raise RuntimeError(self.last_error) from exc

            self.running = True
            return self.status()

    def stop(self) -> Dict[str, Any]:
        with self.stream_lock:
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as exc:
                    self.last_error = f"Audio input stop failed: {exc}"
                finally:
                    self.stream = None

            self.running = False
            self._cancel_note_timers()
            self._close_midi()
            return self.status()

    def available_midi_outputs(self) -> Dict[str, Any]:
        try:
            import mido

            return {"available": True, "ports": mido.get_output_names()}
        except Exception as exc:
            return {"available": False, "ports": [], "error": str(exc)}

    def _setup_midi(self, midi_port_name: Optional[str]) -> None:
        self._close_midi()

        try:
            import mido
        except Exception as exc:
            self.midi_enabled = False
            self.midi_port = None
            self.midi_port_name = None
            self.last_error = f"MIDI output unavailable: {exc}"
            return

        try:
            port_name = midi_port_name
            if not port_name:
                names = mido.get_output_names()
                port_name = names[0] if names else None

            if port_name:
                self.midi_port = mido.open_output(port_name)
                self.midi_enabled = True
                self.midi_port_name = port_name
            else:
                self.midi_enabled = False
                self.midi_port = None
                self.midi_port_name = None
                self.last_error = "No MIDI output ports found. Running in monitor mode."
        except Exception as exc:
            self.midi_enabled = False
            self.midi_port = None
            self.midi_port_name = None
            self.last_error = f"Could not open MIDI output: {exc}"

    def _close_midi(self) -> None:
        if self.midi_port is not None:
            try:
                self.midi_port.close()
            except Exception:
                pass
        self.midi_port = None
        self.midi_enabled = False
        self.midi_port_name = None

    def _cancel_note_timers(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()

    def _audio_callback(self, indata, frames, callback_time, status) -> None:
        if status:
            self.last_error = str(status)

        frame = np.copy(indata[:, 0]).astype(np.float32)

        try:
            self.process_audio(frame)
        except Exception as exc:
            self.last_error = f"Frame processing failed: {exc}"

    def process_audio(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        energy = float(np.mean(frame ** 2))
        peak = float(np.max(np.abs(frame))) if len(frame) else 0.0

        if not self.detect_anomaly(energy, peak):
            return None

        now = time.time()
        if now - self.last_trigger_time < self.config.cooldown_sec:
            return None

        frequency = self.detect_pitch(frame)
        if frequency is None or not np.isfinite(frequency):
            return None

        midi_note = self.freq_to_midi(frequency)
        if midi_note is None:
            return None

        event = {
            "timestamp": time.time(),
            "energy": round(energy, 5),
            "peak": round(peak, 5),
            "frequency_hz": round(float(frequency), 2),
            "midi_note": midi_note,
            "note_name": self.midi_to_name(midi_note),
            "sent_to_midi": self.play_note(midi_note),
        }

        with self.state_lock:
            self.last_trigger_time = now
            self.events_sent += 1
            self.last_event = event

        return event

    def detect_anomaly(self, energy: float, peak: float) -> bool:
        return energy >= self.config.energy_threshold or peak >= self.config.peak_threshold

    def detect_pitch(self, frame: np.ndarray) -> Optional[float]:
        if len(frame) == 0:
            return None

        centered = frame - np.mean(frame)
        if np.max(np.abs(centered)) < 1e-4:
            return None

        windowed = centered * np.hanning(len(centered))
        autocorr = np.correlate(windowed, windowed, mode="full")[len(windowed) - 1 :]

        min_lag = max(1, int(self.config.sample_rate / self.config.pitch_max_hz))
        max_lag = min(len(autocorr) - 1, int(self.config.sample_rate / self.config.pitch_min_hz))
        if max_lag <= min_lag:
            return None

        region = autocorr[min_lag:max_lag]
        if len(region) == 0:
            return None

        peak_index = int(np.argmax(region))
        peak_value = float(region[peak_index])
        if peak_value <= 0:
            return None

        lag = peak_index + min_lag
        return self.config.sample_rate / lag

    def freq_to_midi(self, frequency: float) -> Optional[int]:
        if frequency <= 0:
            return None

        midi = int(round(69 + 12 * math.log2(frequency / 440.0)))
        return max(0, min(127, midi))

    def midi_to_name(self, midi_note: int) -> str:
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (midi_note // 12) - 1
        return f"{notes[midi_note % 12]}{octave}"

    def play_note(self, midi_note: int) -> bool:
        if not self.midi_enabled or self.midi_port is None:
            return False

        try:
            import mido

            note_on = mido.Message("note_on", note=midi_note, velocity=self.config.note_velocity)
            note_off = mido.Message("note_off", note=midi_note, velocity=0)
            self.midi_port.send(note_on)

            timer = threading.Timer(self.config.note_duration_sec, self.midi_port.send, args=(note_off,))
            timer.daemon = True
            timer.start()
            self._timers.append(timer)
            return True
        except Exception as exc:
            self.last_error = f"MIDI send failed: {exc}"
            return False
