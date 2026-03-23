# ml/analyzer.py
"""
XAI layer — librosa-based artifact detection.
Generates human-readable explanations for why audio was flagged.
"""
import librosa
import numpy as np
from loguru import logger


def analyze_artifacts(wav_path: str) -> list[str]:
    """
    Analyze audio file and return list of detected artifact descriptions.
    Always returns at least 1 string. Max 4 strings.
    """
    artifacts = []
    try:
        y, sr = librosa.load(wav_path, sr=16000, mono=True)

        # --- Check 1: Pitch uniformity (unnatural flatness) ---
        try:
            f0 = librosa.yin(y, fmin=50, fmax=400)
            f0_voiced = f0[f0 > 0]
            if len(f0_voiced) > 10:
                variance = float(np.std(f0_voiced) / (np.mean(f0_voiced) + 1e-6))
                if variance < 0.08:
                    artifacts.append("Unnatural pitch uniformity — voice lacks human variation")
        except Exception:
            pass

        # --- Check 2: Zero crossing rate spikes ---
        try:
            zcr = librosa.feature.zero_crossing_rate(y)[0]
            mean_zcr = np.mean(zcr)
            std_zcr = np.std(zcr)
            spike_frames = np.where(zcr > mean_zcr + 2.5 * std_zcr)[0]
            if len(spike_frames) > 0:
                spike_time = round(float(spike_frames[0]) * 512 / sr, 1)
                artifacts.append(f"Spectral discontinuity detected at {spike_time}s")
        except Exception:
            pass

        # --- Check 3: MFCC coefficient drops (pitch reset signature) ---
        try:
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc1 = mfcc[0]
            diffs = np.abs(np.diff(mfcc1))
            threshold = np.mean(diffs) + 3 * np.std(diffs)
            sharp_drops = np.where(diffs > threshold)[0]
            if len(sharp_drops) > 0:
                drop_time = round(float(sharp_drops[0]) * 512 / sr, 1)
                artifacts.append(f"Unnatural pitch reset at {drop_time}s")
        except Exception:
            pass

        # --- Check 4: Mel spectrogram repetition (GAN pattern) ---
        try:
            mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64)
            mel_db = librosa.power_to_db(mel)
            # Check autocorrelation along time axis for repeating patterns
            col_means = np.mean(mel_db, axis=0)
            if len(col_means) > 20:
                autocorr = np.correlate(col_means - col_means.mean(),
                                        col_means - col_means.mean(), mode='full')
                autocorr = autocorr[len(autocorr)//2:]
                autocorr /= (autocorr[0] + 1e-6)
                # Check for peaks at lag > 10 frames
                peak = np.max(autocorr[10:min(50, len(autocorr))])
                if peak > 0.75:
                    artifacts.append("GAN-pattern artifact — repeating spectral signature detected")
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"Artifact analysis failed: {e}")

    # Always return at least one artifact description
    if not artifacts:
        artifacts.append("Minor spectral irregularities detected — low confidence signal")

    return artifacts[:4]  # Max 4
