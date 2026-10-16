"""Bounded PCM WAV importer for ARM9 8-bit DS hardware playback."""
from pathlib import Path
import wave

MAX_SOUND_BYTES=32768
MAX_TOTAL_BYTES=131072

def convert_wav(path):
    try:
        with wave.open(str(path),'rb') as wf:
            channels=wf.getnchannels()
            width=wf.getsampwidth()
            rate=wf.getframerate()
            frames=wf.getnframes()
            if channels not in (1,2) or width not in (1,2):
                raise ValueError('WAV must be mono/stereo 8-bit or 16-bit PCM')
            if rate<8000 or rate>32768:raise ValueError('WAV sample rate must be 8000..32768 Hz')
            if frames>MAX_SOUND_BYTES:raise ValueError('WAV too long: max 32768 samples per sound')
            raw=wf.readframes(frames)
    except wave.Error as err:
        raise ValueError(f'Unsupported WAV encoding (use uncompressed PCM): {err}') from err
    if len(raw)!=frames*width*channels:raise ValueError('Truncated WAV sample data')
    out=bytearray()
    for i in range(frames):
        acc=0
        for c in range(channels):
            off=(i*channels+c)*width
            if width==1: signed=raw[off]-128
            else: signed=int.from_bytes(raw[off:off+2],'little',signed=True)//256
            acc+=signed
        out.append((acc//channels)&255)
    # Aligned payload for DS audio DMA, with actual length carried separately.
    out.extend(b'\x00'*((-len(out))%4))
    return bytes(out),frames,rate
