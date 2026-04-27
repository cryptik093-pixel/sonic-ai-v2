"""
Pyramid resonance engine.

This module listens to ambient audio, derives simple environmental features,
and turns them into a text phrase plus a modal melody recipe inspired by the
long, reflective acoustics associated with the King's Chamber.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

import numpy as np
import sounddevice as sd


@dataclass
class PyramidConfig:
    sample_rate: int = 44100
    block_size: int = 2048
    analysis_window_sec: float = 8.0
    trigger_rms: float = 0.015
    target_decay_sec: float = 7.2
    target_pre_delay_ms: float = 95.0
    target_resonance_hz: float = 121.0


class PyramidResonanceEngine:
    def __init__(self, config: Optional[PyramidConfig] = None) -> None:
        self.config = config or PyramidConfig()
        self.stream = None
        self.stream_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.running = False
        self.last_error: Optional[str] = None
        self.last_frame_at: Optional[float] = None
        self.last_capture: Optional[Dict[str, Any]] = None
        self.capture_count = 0
        self.audio_buffer: Deque[np.ndarray] = deque()
        self.max_buffer_samples = int(self.config.sample_rate * self.config.analysis_window_sec)

    def status(self) -> Dict[str, Any]:
        with self.state_lock:
            buffered_samples = int(sum(len(chunk) for chunk in self.audio_buffer))
            return {
                "running": self.running,
                "sample_rate": self.config.sample_rate,
                "block_size": self.config.block_size,
                "analysis_window_sec": self.config.analysis_window_sec,
                "target_decay_sec": self.config.target_decay_sec,
                "target_pre_delay_ms": self.config.target_pre_delay_ms,
                "target_resonance_hz": self.config.target_resonance_hz,
                "buffered_seconds": round(buffered_samples / self.config.sample_rate, 2),
                "capture_count": self.capture_count,
                "last_frame_at": self.last_frame_at,
                "last_error": self.last_error,
                "last_capture": self.last_capture,
            }

    def start(self) -> Dict[str, Any]:
        with self.stream_lock:
            if self.running:
                return self.status()

            self.last_error = None
            self.audio_buffer.clear()

            try:
                self.stream = sd.InputStream(
                    callback=self._audio_callback,
                    channels=1,
                    samplerate=self.config.sample_rate,
                    blocksize=self.config.block_size,
                )
                self.stream.start()
            except Exception as exc:
                self.stream = None
                self.running = False
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
            return self.status()

    def _audio_callback(self, indata, frames, callback_time, status) -> None:
        if status:
            self.last_error = str(status)

        frame = np.copy(indata[:, 0]).astype(np.float32)
        self._store_frame(frame)

    def _store_frame(self, frame: np.ndarray) -> None:
        with self.state_lock:
            self.audio_buffer.append(frame)
            self.last_frame_at = time.time()

            total_samples = sum(len(chunk) for chunk in self.audio_buffer)
            while total_samples > self.max_buffer_samples and self.audio_buffer:
                removed = self.audio_buffer.popleft()
                total_samples -= len(removed)

    def capture_resonance(self, sensors: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        sensors = sensors or {}
        frame = self._snapshot_audio()
        analysis = self._analyze_audio(frame)
        capture = self._build_capture_payload(analysis, sensors)

        with self.state_lock:
            self.capture_count += 1
            self.last_capture = capture

        return capture

    def _snapshot_audio(self) -> np.ndarray:
        with self.state_lock:
            if not self.audio_buffer:
                raise RuntimeError("No ambient audio captured yet. Start listening first.")

            return np.concatenate(list(self.audio_buffer))

    def _analyze_audio(self, audio: np.ndarray) -> Dict[str, Any]:
        centered = audio - np.mean(audio)
        if np.max(np.abs(centered)) < 1e-6:
            raise RuntimeError("Ambient signal is too quiet to analyze.")

        window = np.hanning(len(centered))
        windowed = centered * window
        spectrum = np.abs(np.fft.rfft(windowed))
        freqs = np.fft.rfftfreq(len(windowed), 1 / self.config.sample_rate)

        rms = float(np.sqrt(np.mean(centered ** 2)))
        peak = float(np.max(np.abs(centered)))

        dominant_index = int(np.argmax(spectrum[1:]) + 1) if len(spectrum) > 1 else 0
        dominant_freq = float(freqs[dominant_index]) if dominant_index < len(freqs) else 0.0

        centroid = self._spectral_centroid(freqs, spectrum)
        spread = self._spectral_spread(freqs, spectrum, centroid)
        band_profile = self._band_profile(freqs, spectrum)
        resonance_alignment = max(
            0.0,
            1.0 - min(abs(dominant_freq - self.config.target_resonance_hz) / self.config.target_resonance_hz, 1.0),
        )

        return {
            "rms": round(rms, 5),
            "peak": round(peak, 5),
            "dominant_freq_hz": round(dominant_freq, 2),
            "spectral_centroid_hz": round(centroid, 2),
            "spectral_spread_hz": round(spread, 2),
            "band_profile": band_profile,
            "resonance_alignment": round(resonance_alignment, 3),
            "intensity": self._intensity_label(rms, peak),
            "texture": self._texture_label(centroid, spread),
        }

    def _spectral_centroid(self, freqs: np.ndarray, spectrum: np.ndarray) -> float:
        magnitude_sum = float(np.sum(spectrum))
        if magnitude_sum <= 0:
            return 0.0
        return float(np.sum(freqs * spectrum) / magnitude_sum)

    def _spectral_spread(self, freqs: np.ndarray, spectrum: np.ndarray, centroid: float) -> float:
        magnitude_sum = float(np.sum(spectrum))
        if magnitude_sum <= 0:
            return 0.0
        variance = np.sum(((freqs - centroid) ** 2) * spectrum) / magnitude_sum
        return float(math.sqrt(max(variance, 0.0)))

    def _band_profile(self, freqs: np.ndarray, spectrum: np.ndarray) -> Dict[str, float]:
        def band_energy(low: float, high: float) -> float:
            mask = (freqs >= low) & (freqs < high)
            return float(np.sum(spectrum[mask]))

        low = band_energy(20, 180)
        low_mid = band_energy(180, 600)
        presence = band_energy(600, 2000)
        air = band_energy(2000, 8000)
        total = max(low + low_mid + presence + air, 1e-9)

        return {
            "low": round((low / total) * 100, 1),
            "low_mid": round((low_mid / total) * 100, 1),
            "presence": round((presence / total) * 100, 1),
            "air": round((air / total) * 100, 1),
        }

    def _intensity_label(self, rms: float, peak: float) -> str:
        if peak > 0.45 or rms > 0.09:
            return "surging"
        if peak > 0.20 or rms > 0.04:
            return "present"
        if peak > 0.07 or rms > 0.015:
            return "hushed"
        return "faint"

    def _texture_label(self, centroid: float, spread: float) -> str:
        if centroid < 220:
            return "stone-like"
        if centroid < 700:
            return "chambered"
        if spread > 1800:
            return "shimmering"
        return "airy"

    def _build_capture_payload(self, analysis: Dict[str, Any], sensors: Dict[str, Any]) -> Dict[str, Any]:
        sensor_state = self._normalize_sensors(sensors)
        melody = self._generate_melody(analysis, sensor_state)
        phrase = self._generate_phrase(analysis, sensor_state, melody)

        capture = {
            "timestamp": time.time(),
            "analysis": analysis,
            "sensor_state": sensor_state,
            "phrase": phrase,
            "melody": melody,
            "pyramid_acoustics": {
                "inspiration": "King's Chamber-inspired long decay and low resonance emphasis",
                "target_decay_sec": self.config.target_decay_sec,
                "target_pre_delay_ms": self.config.target_pre_delay_ms,
                "resonance_focus_hz": self.config.target_resonance_hz,
                "recommended_effect_chain": [
                    "high-pass at 45 Hz",
                    "narrow boost near 121 Hz",
                    "plate or stone-chamber reverb with 7.2 s decay",
                    "pre-delay around 95 ms",
                    "gentle stereo widening after the reverb tail",
                ],
            },
        }
        return capture

    def _normalize_sensors(self, sensors: Dict[str, Any]) -> Dict[str, float]:
        def clamp(name: str, default: float) -> float:
            try:
                value = float(sensors.get(name, default))
            except (TypeError, ValueError):
                value = default
            return max(0.0, min(1.0, value))

        return {
            "motion": clamp("motion", 0.25),
            "light": clamp("light", 0.35),
            "temperature": clamp("temperature", 0.5),
            "humidity": clamp("humidity", 0.4),
        }

    def _generate_melody(self, analysis: Dict[str, Any], sensors: Dict[str, float]) -> Dict[str, Any]:
        mode = "Phrygian dominant" if sensors["light"] < 0.45 else "Dorian"
        root = self._select_root(analysis["dominant_freq_hz"])
        intervals = [0, 1, 4, 5, 7, 8, 10] if mode == "Phrygian dominant" else [0, 2, 3, 5, 7, 9, 10]
        steps = 5 + int(round(sensors["motion"] * 3))
        register = 48 if analysis["band_profile"]["low"] > 28 else 60

        notes: List[Dict[str, Any]] = []
        for idx in range(steps):
            interval = intervals[(idx + int(analysis["resonance_alignment"] * 3)) % len(intervals)]
            midi_note = register + root + interval + (12 if idx % 3 == 2 else 0)
            duration = round(0.6 + sensors["humidity"] * 0.5 + (analysis["resonance_alignment"] * 0.4), 2)
            velocity = int(52 + sensors["motion"] * 22 + analysis["band_profile"]["presence"] * 0.15)
            notes.append(
                {
                    "step": idx + 1,
                    "midi_note": int(midi_note),
                    "note_name": self._midi_to_name(int(midi_note)),
                    "duration_sec": duration,
                    "velocity": max(1, min(127, velocity)),
                }
            )

        return {
            "title": f"{self._midi_to_name(register + root)} {mode} chamber line",
            "mode": mode,
            "root_note": self._midi_to_name(register + root),
            "tempo_bpm": int(52 + analysis["band_profile"]["presence"] * 0.35 + sensors["motion"] * 18),
            "notes": notes,
        }

    def _generate_phrase(
        self,
        analysis: Dict[str, Any],
        sensors: Dict[str, float],
        melody: Dict[str, Any],
    ) -> str:
        openings = {
            "surging": "Stone answers in a rising wave",
            "present": "A measured echo moves through the chamber",
            "hushed": "A quiet resonance circles the granite air",
            "faint": "The chamber listens before it speaks",
        }

        textures = {
            "stone-like": "with a low mineral bloom",
            "chambered": "with a hollow vaulted bloom",
            "shimmering": "with bright reflected edges",
            "airy": "with a lifted breath of overtones",
        }

        sensor_tail = "slow and ceremonial" if sensors["motion"] < 0.35 else "alert and processional"
        return (
            f"{openings[analysis['intensity']]}, {textures[analysis['texture']]}, "
            f"settling into {melody['root_note']} {melody['mode']} at {melody['tempo_bpm']} BPM, "
            f"{sensor_tail} like music waking the King's Chamber."
        )

    def _select_root(self, dominant_freq: float) -> int:
        if dominant_freq <= 0:
            return 0

        midi = int(round(69 + 12 * math.log2(max(dominant_freq, 1.0) / 440.0)))
        return midi % 12

    def _midi_to_name(self, midi_note: int) -> str:
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (midi_note // 12) - 1
        return f"{notes[midi_note % 12]}{octave}"
