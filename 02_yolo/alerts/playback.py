"""PortAudio device-clock onset estimate, including leading PCM silence."""

from threading import Event

import numpy as np
from yolo.alerts.timing import host_time


class SoundDevicePlayback:
    measurement_method = "portaudio_dac_estimate_first_non_silent_pcm"

    def __init__(self, device=None, *, clock=host_time):
        self.device = device
        self.clock = clock

    def play(self, clip, on_start, cancel):
        import sounddevice as sd

        samples = np.frombuffer(clip.pcm, dtype="<i2").reshape(-1, clip.channels)
        non_silent = np.flatnonzero(
            np.any(np.abs(samples.astype(np.int32)) >= 64, axis=1)
        )
        if not len(non_silent):
            raise ValueError("voice clip contains no measurable non-silent PCM")
        first_sample = int(non_silent[0])
        finished = Event()
        onset: list[float] = []
        failures: list[str] = []
        cursor = 0

        def callback(outdata, frames, time_info, status):
            nonlocal cursor
            if cancel.is_set():
                raise sd.CallbackAbort
            if status.output_underflow:
                failures.append("audio output underflow")
                raise sd.CallbackAbort
            size = frames * clip.channels * 2
            block = clip.pcm[
                cursor * clip.channels * 2 : (cursor + frames) * clip.channels * 2
            ]
            outdata[:] = block + b"\0" * (size - len(block))
            if not onset and cursor <= first_sample < cursor + frames:
                onset.append(
                    self.clock()
                    + max(0.0, time_info.outputBufferDacTime - time_info.currentTime)
                    + (first_sample - cursor) / clip.sample_rate
                )
            cursor += frames
            if cursor >= len(samples):
                raise sd.CallbackStop

        with sd.RawOutputStream(
            samplerate=clip.sample_rate,
            channels=clip.channels,
            dtype="int16",
            device=self.device,
            callback=callback,
            finished_callback=finished.set,
        ):
            deadline = self.clock() + len(samples) / clip.sample_rate + 5
            reported = False
            while not finished.wait(0.02):
                if onset and not reported:
                    on_start(onset[0], self.measurement_method)
                    reported = True
                if self.clock() > deadline:
                    raise TimeoutError("audio playback did not finish")
            if onset and not reported and not cancel.is_set():
                on_start(onset[0], self.measurement_method)
            if not onset and not cancel.is_set():
                raise RuntimeError(
                    "audio ended before a non-silent sample was scheduled"
                )
            if failures:
                raise RuntimeError(failures[0])
