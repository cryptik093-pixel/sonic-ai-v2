"""Fast bounded analyzer with metadata consensus and file-hash caching."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime

import librosa
import numpy as np
import sounddevice as sd
from scipy import signal

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


class SonicAnalyzer:
    _analysis_cache = {}

    def __init__(self, sample_rate=22050, duration=5, enable_caching=True, max_analysis_duration_seconds=20):
        self.sample_rate = sample_rate
        self.duration = duration
        self.enable_caching = enable_caching
        self.max_analysis_duration_seconds = max_analysis_duration_seconds
        self.reference_profiles = {
            "pop": {"low": 35, "mid": 45, "high": 20},
            "hiphop": {"low": 50, "mid": 35, "high": 15},
            "rock": {"low": 40, "mid": 40, "high": 20},
            "electronic": {"low": 45, "mid": 35, "high": 20},
            "classical": {"low": 25, "mid": 50, "high": 25},
        }
        self.audio = None
        self.fft_data = None
        self.frequencies = None
        self.file_hash = None
        self.results = {}
        self._reset()

    def _reset(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "analysis_duration_seconds": 0.0,
            "key": "Key uncertain",
            "key_confidence": 0.0,
            "tempo": None,
            "tempo_confidence": 0.0,
            "tempo_label": "BPM uncertain",
            "chord": None,
            "chord_confidence": 0.0,
            "mix_balance": {"low": 0, "mid": 0, "high": 0},
            "lufs": 0.0,
            "harmonic_complexity": 0.0,
            "melodic_contour": "Unknown",
            "pitch_distribution": {},
            "spectral_peaks": [],
            "mix_reference": None,
            "mix_reference_diff": None,
            "loudness_category": None,
            "metadata_confidence": 0.0,
            "metadata_status": "uncertain",
            "source_votes": {"tempo": [], "key": []},
            "notes": [],
            "cache_hit": False,
            "file_hash": None,
        }

    def _json_safe(self, value):
        if isinstance(value, dict):
            return {k: self._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._json_safe(v) for v in value]
        if isinstance(value, np.ndarray):
            return [self._json_safe(v) for v in value.tolist()]
        if isinstance(value, np.generic):
            return value.item()
        return value

    def _hash_file(self, filepath):
        hasher = hashlib.sha256()
        with open(filepath, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def record_audio(self, device_id=5):
        self.audio = sd.rec(int(self.duration * self.sample_rate), samplerate=self.sample_rate, channels=1, device=device_id)
        sd.wait()
        self.audio = self.audio.flatten().astype(np.float32)
        return self.audio

    def load_audio(self, audio_array):
        self.audio = np.asarray(audio_array, dtype=np.float32).flatten()
        return self.audio

    def load_file(self, filepath):
        self.file_hash = self._hash_file(filepath)
        audio, sr = librosa.load(
            filepath,
            sr=self.sample_rate,
            mono=True,
            duration=self.max_analysis_duration_seconds,
            res_type="kaiser_fast",
        )
        self.sample_rate = sr
        self.audio = np.ascontiguousarray(audio, dtype=np.float32)
        self.results["analysis_duration_seconds"] = round(len(self.audio) / sr, 3) if sr else 0.0
        self.results["file_hash"] = self.file_hash
        return self.audio

    def preprocess(self):
        if self.audio is None:
            raise ValueError("No audio loaded")
        self.audio = self.audio - np.mean(self.audio)
        peak = np.max(np.abs(self.audio)) if self.audio.size else 0.0
        if peak > 0:
            self.audio = self.audio / peak
        return self.audio

    def spectral_analysis(self, num_peaks=24):
        if self.audio is None or not self.audio.size:
            self.fft_data, self.frequencies = np.array([]), np.array([])
            return np.array([])
        window = np.hanning(len(self.audio))
        audio_windowed = self.audio * window
        self.fft_data = np.abs(np.fft.rfft(audio_windowed))
        self.frequencies = np.fft.rfftfreq(len(audio_windowed), 1 / self.sample_rate)
        valid = (self.frequencies > 60) & (self.frequencies < 4000)
        filtered_fft = self.fft_data[valid]
        filtered_freqs = self.frequencies[valid]
        if not filtered_fft.size:
            return np.array([])
        peak_count = min(num_peaks, len(filtered_fft))
        peak_indices = np.argsort(filtered_fft)[::-1][:peak_count]
        self.results["spectral_peaks"] = [{"freq": float(filtered_freqs[i]), "magnitude": float(filtered_fft[i])} for i in peak_indices]
        return filtered_freqs[peak_indices]

    def pitch_detection(self, detected_freqs):
        pitch_classes = []
        pitch_dist = np.zeros(12)
        for freq in detected_freqs:
            if freq <= 0:
                continue
            midi_num = 12 * np.log2(freq / 440.0) + 69
            pitch_class = (round(midi_num) - 12) % 12
            pitch_classes.append(pitch_class)
            pitch_dist[pitch_class] += 1
        if np.sum(pitch_dist) > 0:
            pitch_dist = (pitch_dist / np.sum(pitch_dist)) * 100
        self.results["pitch_distribution"] = {NOTE_NAMES[i]: round(float(pitch_dist[i]), 1) for i in range(12) if pitch_dist[i] > 0}
        return pitch_classes, pitch_dist

    def _best_key_from_vector(self, vector):
        if not np.any(vector):
            return None, 0.0
        vector = vector / (np.linalg.norm(vector) + 1e-10)
        best_name, best_score, second_best = None, -1.0, -1.0
        for index, note_name in enumerate(NOTE_NAMES):
            major_score = np.corrcoef(vector, np.roll(MAJOR, index) / np.linalg.norm(MAJOR))[0, 1]
            minor_score = np.corrcoef(vector, np.roll(MINOR, index) / np.linalg.norm(MINOR))[0, 1]
            for name, score in ((f"{note_name} Major", major_score), (f"{note_name} Minor", minor_score)):
                if score > best_score:
                    second_best, best_score, best_name = best_score, score, name
                elif score > second_best:
                    second_best = score
        confidence = max(0.0, min(1.0, float(best_score - max(second_best, 0.0)) + 0.45))
        return best_name, confidence

    def detect_key(self, pitch_dist):
        votes = []
        base_name, base_conf = self._best_key_from_vector(np.asarray(pitch_dist, dtype=np.float32))
        if base_name:
            votes.append({"source": "pitch_profile", "value": base_name, "confidence": round(base_conf, 3)})
        if self.audio is not None and self.audio.size:
            harmonic = librosa.effects.harmonic(self.audio)
            for source_name, chroma in (
                ("chroma_cqt", librosa.feature.chroma_cqt(y=harmonic, sr=self.sample_rate)),
                ("chroma_stft", librosa.feature.chroma_stft(y=harmonic, sr=self.sample_rate)),
            ):
                key_name, confidence = self._best_key_from_vector(np.mean(chroma, axis=1))
                if key_name:
                    votes.append({"source": source_name, "value": key_name, "confidence": round(confidence, 3)})
        totals = {}
        for vote in votes:
            totals[vote["value"]] = totals.get(vote["value"], 0.0) + vote["confidence"]
        final_key, final_confidence = "Key uncertain", 0.0
        if totals:
            final_key = max(totals.items(), key=lambda item: item[1])[0]
            final_confidence = totals[final_key] / max(len(votes), 1)
            disagree = len({vote["value"] for vote in votes}) > 1
            if final_confidence < 0.55 or (disagree and final_confidence < 0.72):
                final_key = "Key uncertain"
        self.results["key"] = final_key
        self.results["key_confidence"] = round(float(final_confidence), 3)
        self.results["source_votes"]["key"] = votes
        if final_key == "Key uncertain":
            self.results["notes"].append("Key uncertain")
        return final_key, final_confidence

    def _normalize_tempo(self, bpm, min_bpm=70, max_bpm=160):
        if bpm is None or bpm <= 0 or not np.isfinite(bpm):
            return None
        while bpm < min_bpm:
            bpm *= 2
        while bpm > max_bpm:
            bpm /= 2
        return round(float(bpm), 2)

    def _bucket_tempo(self, bpm):
        return int(round(float(bpm) / 2.0) * 2)

    def _heuristic_tempo(self):
        hop = 512
        if self.audio is None or not self.audio.size:
            return None, 0.0
        energy = np.asarray([np.sum(self.audio[i:i + hop] ** 2) for i in range(0, max(0, len(self.audio) - hop), hop)], dtype=np.float32)
        if not energy.size:
            return None, 0.0
        novelty = np.maximum(0, np.diff(signal.medfilt(energy, kernel_size=3), prepend=energy[0]))
        threshold = np.mean(novelty) + 1.2 * np.std(novelty)
        onsets = np.where(novelty > threshold)[0]
        if len(onsets) < 2:
            return None, 0.0
        iois = np.diff(onsets * hop / self.sample_rate)
        valid = iois[(iois >= 60 / 160) & (iois <= 60 / 70)]
        if not len(valid):
            return None, 0.0
        return self._normalize_tempo(60 / float(np.median(valid))), min(1.0, 0.45 + min(len(valid), 12) / 20)

    def detect_bpm(self):
        votes = []
        heuristic_tempo, heuristic_conf = self._heuristic_tempo()
        if heuristic_tempo:
            votes.append({"source": "energy_onsets", "value": heuristic_tempo, "confidence": round(heuristic_conf, 3)})
        onset_env = librosa.onset.onset_strength(y=self.audio, sr=self.sample_rate) if self.audio is not None else np.array([])
        if onset_env.size:
            tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=self.sample_rate)
            librosa_tempo = self._normalize_tempo(float(tempo))
            if librosa_tempo:
                votes.append({"source": "librosa_beat_track", "value": librosa_tempo, "confidence": 0.75})
            autocorr = librosa.autocorrelate(onset_env, max_size=min(len(onset_env), 2048))
            min_lag = max(1, int(round(librosa.time_to_frames(60 / 160, sr=self.sample_rate))))
            max_lag = max(min_lag + 1, int(round(librosa.time_to_frames(60 / 70, sr=self.sample_rate))))
            window = autocorr[min_lag:max_lag]
            if window.size:
                lag = int(np.argmax(window)) + min_lag
                seconds = librosa.frames_to_time(1, sr=self.sample_rate) * lag
                autocorr_tempo = self._normalize_tempo(60 / seconds if seconds > 0 else None)
                if autocorr_tempo:
                    confidence = float(window.max() / (autocorr.max() + 1e-10))
                    votes.append({"source": "onset_autocorr", "value": autocorr_tempo, "confidence": round(min(1.0, confidence), 3)})
        grouped = {}
        for vote in votes:
            bucket = self._bucket_tempo(vote["value"])
            grouped.setdefault(bucket, {"score": 0.0, "values": []})
            grouped[bucket]["score"] += vote["confidence"]
            grouped[bucket]["values"].append(vote["value"])
        final_tempo, final_confidence = None, 0.0
        if grouped:
            best_bucket, best_entry = max(grouped.items(), key=lambda item: item[1]["score"])
            final_tempo = round(float(np.median(best_entry["values"])))
            final_confidence = best_entry["score"] / max(len(votes), 1)
            if final_confidence < 0.55 or (len(grouped) > 1 and final_confidence < 0.72):
                final_tempo = None
        self.results["tempo"] = final_tempo
        self.results["tempo_confidence"] = round(float(final_confidence), 3)
        self.results["tempo_label"] = f"{final_tempo} BPM" if final_tempo else "BPM uncertain"
        self.results["source_votes"]["tempo"] = votes
        if final_tempo is None:
            self.results["notes"].append("BPM uncertain")
        return final_tempo, final_confidence

    def identify_chord(self, pitch_classes):
        if not pitch_classes:
            return None, 0.0
        templates = {
            "Major": [0, 4, 7],
            "Minor": [0, 3, 7],
            "Major 7": [0, 4, 7, 11],
            "Dominant 7": [0, 4, 7, 10],
            "Minor 7": [0, 3, 7, 10],
            "Diminished": [0, 3, 6],
            "Augmented": [0, 4, 8],
        }
        root_pc = Counter(pitch_classes).most_common(1)[0][0]
        counts = np.zeros(12)
        for pitch_class in pitch_classes:
            counts[pitch_class] += 1
        best_chord, best_score = "Major", 0
        for chord_name, intervals in templates.items():
            score = sum(1 for pitch_class in [(root_pc + i) % 12 for i in intervals] if counts[pitch_class] > 0)
            if score > best_score:
                best_chord, best_score = chord_name, score
        confidence = best_score / len(templates[best_chord])
        self.results["chord"] = f"{NOTE_NAMES[root_pc]} {best_chord}"
        self.results["chord_confidence"] = round(min(confidence, 1.0), 3)
        return self.results["chord"], confidence

    def spectral_balance(self):
        if self.fft_data is None or not self.fft_data.size:
            return self.results["mix_balance"]
        bands = {"low": (20, 250), "mid": (250, 2000), "high": (2000, 20000)}
        energies = {}
        for band, (low, high) in bands.items():
            mask = (self.frequencies > low) & (self.frequencies < high)
            energies[band] = float(np.sum(self.fft_data[mask] ** 2))
        total = sum(energies.values())
        if total > 0:
            self.results["mix_balance"] = {band: round(value / total * 100, 1) for band, value in energies.items()}
        diffs = {}
        for name, profile in self.reference_profiles.items():
            diffs[name] = sum(abs(self.results["mix_balance"][band] - profile[band]) for band in profile)
        best = min(diffs.items(), key=lambda item: item[1])
        self.results["mix_reference"], self.results["mix_reference_diff"] = best[0], round(best[1], 1)
        return self.results["mix_balance"]

    def calculate_lufs(self):
        rms = float(np.sqrt(np.mean(self.audio ** 2))) if self.audio is not None and self.audio.size else 0.0
        lufs = 20 * np.log10(max(rms, 1e-10)) - 0.691
        self.results["lufs"] = round(float(lufs), 1)
        self.results["loudness_category"] = "very_loud" if lufs > -6 else "loud" if lufs > -12 else "normal" if lufs > -20 else "quiet" if lufs > -30 else "very_quiet"
        return lufs

    def harmonic_complexity(self, pitch_dist):
        pcd = np.asarray(pitch_dist, dtype=np.float32)
        if np.sum(pcd) <= 0:
            return 0.0
        pcd = pcd / np.sum(pcd)
        entropy = -np.sum(pcd * np.log2(pcd + 1e-10))
        self.results["harmonic_complexity"] = round(float(entropy / np.log2(12)) * 10, 2)
        return self.results["harmonic_complexity"]

    def melodic_contour(self):
        if self.audio is None or not self.audio.size:
            return self.results["melodic_contour"]
        pitches, _ = librosa.piptrack(y=self.audio, sr=self.sample_rate)
        contour = [float(pitches[:, i][np.argmax(pitches[:, i])]) for i in range(pitches.shape[1]) if np.any(pitches[:, i] > 0)]
        if len(contour) < 2:
            self.results["melodic_contour"] = "Flat"
        else:
            delta = contour[-1] - contour[0]
            self.results["melodic_contour"] = "Rising" if delta > 15 else "Falling" if delta < -15 else "Flat"
        return self.results["melodic_contour"]

    def analyze(self, device_id=5, record=True, filepath=None):
        self._reset()
        if filepath and self.enable_caching:
            file_hash = self._hash_file(filepath)
            cached = self._analysis_cache.get(file_hash)
            if cached:
                cached["cache_hit"] = True
                cached["timestamp"] = datetime.now().isoformat()
                return json.loads(json.dumps(cached))
        if filepath:
            self.load_file(filepath)
        elif record:
            self.record_audio(device_id)
        elif self.audio is None:
            raise ValueError("No audio loaded or file specified")
        self.preprocess()
        detected_freqs = self.spectral_analysis()
        pitch_classes, pitch_dist = self.pitch_detection(detected_freqs)
        self.detect_key(pitch_dist)
        self.detect_bpm()
        self.identify_chord(pitch_classes)
        self.spectral_balance()
        self.calculate_lufs()
        self.harmonic_complexity(pitch_dist)
        self.melodic_contour()
        self.results["metadata_confidence"] = round((self.results["tempo_confidence"] + self.results["key_confidence"]) / 2, 3)
        self.results["metadata_status"] = "trusted" if self.results["metadata_confidence"] >= 0.7 else "uncertain"
        self.results = self._json_safe(self.results)
        if filepath and self.enable_caching and self.file_hash:
            self._analysis_cache[self.file_hash] = json.loads(json.dumps(self.results))
        return self.results

    def get_json(self):
        return json.dumps(self._json_safe(self.results), indent=2)

    def get_dict(self):
        return self._json_safe(self.results)

    def print_report(self):
        print(self.get_json())


def main():
    analyzer = SonicAnalyzer()
    analyzer.analyze(device_id=5, record=True)
    analyzer.print_report()


if __name__ == "__main__":
    main()
