import tempfile
import wave
from pathlib import Path
from typing import Optional

SAMPLE_RATE = 16000
CHANNELS = 1


def has_input_device() -> bool:
    """
    Chequea si hay al menos un micrófono disponible en este equipo,
    sin necesidad de empezar a grabar. Se usa en Acerca de para avisar
    de antemano si el chat de voz va a poder usarse.
    """
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        return any(device.get("max_input_channels", 0) > 0 for device in devices)
    except Exception:
        return False


class AudioRecordingError(Exception):
    pass


class AudioRecorder:

    def __init__(self) -> None:
        self._stream = None
        self._frames: list = []
        self._recording = False

    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if self._recording:
            raise AudioRecordingError("Ya hay una grabación en curso.")

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioRecordingError(
                "Falta el paquete 'sounddevice' para grabar audio (pip install sounddevice)."
            ) from exc

        self._frames = []

        def callback(indata, _frames, _time_info, _status) -> None:
            self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=callback
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise AudioRecordingError(
                f"No se pudo acceder al micrófono: {exc}. Revisá que haya uno conectado y "
                "que la app tenga permiso para usarlo."
            ) from exc

        self._recording = True

    def stop(self, output_path: Optional[Path] = None) -> Path:
        if not self._recording or self._stream is None:
            raise AudioRecordingError("No hay una grabación en curso.")

        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._recording = False

        if not self._frames:
            raise AudioRecordingError("No se grabó ningún audio.")

        try:
            import numpy as np
        except ImportError as exc:
            raise AudioRecordingError(
                "Falta el paquete 'numpy' para procesar el audio grabado (pip install numpy)."
            ) from exc

        audio_data = np.concatenate(self._frames, axis=0)
        self._frames = []

        if output_path is None:
            fd, tmp_name = tempfile.mkstemp(suffix=".wav", prefix="vicky_dictado_")
            import os

            os.close(fd)
            output_path = Path(tmp_name)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        return output_path

    def cancel(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._frames = []
        self._recording = False
