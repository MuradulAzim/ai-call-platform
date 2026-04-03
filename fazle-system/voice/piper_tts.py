# ============================================================
# Piper TTS adapter for LiveKit Agents VoicePipelineAgent
# Local, fast, zero-latency text-to-speech using ONNX models
# ============================================================
import asyncio
import io
import logging
import wave
from typing import Optional

import httpx
from livekit import rtc
from livekit.agents import tts, utils
from livekit.agents.types import APIConnectOptions

logger = logging.getLogger("piper-tts")


class PiperTTS(tts.TTS):
    """LiveKit-compatible TTS using local Piper ONNX voice models."""

    def __init__(self, *, model_path: str):
        from piper import PiperVoice

        self._voice = PiperVoice.load(model_path)
        sample_rate = self._voice.config.sample_rate

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        logger.info(f"Piper TTS loaded: {model_path} (sample_rate={sample_rate})")

    def synthesize(
        self,
        text: str,
        *,
        conn_options: Optional[APIConnectOptions] = None,
    ) -> "PiperChunkedStream":
        return PiperChunkedStream(tts=self, input_text=text, voice=self._voice)


class PiperChunkedStream(tts.ChunkedStream):
    """Wraps Piper synthesis as a LiveKit ChunkedStream."""

    def __init__(
        self,
        *,
        tts: PiperTTS,
        input_text: str,
        voice,
    ):
        super().__init__(tts=tts, input_text=input_text)
        self._voice = voice

    async def _run(self) -> None:
        def _synthesize():
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                self._voice.synthesize(self._input_text, wf)
            buf.seek(0)
            with wave.open(buf, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                pcm = wf.readframes(n_frames)
            return pcm, sample_rate, n_frames

        pcm, sample_rate, samples = await asyncio.get_event_loop().run_in_executor(
            None, _synthesize
        )

        frame = rtc.AudioFrame(
            data=pcm,
            sample_rate=sample_rate,
            num_channels=1,
            samples_per_channel=samples,
        )

        self._event_ch.send_nowait(
            tts.SynthesizedAudio(
                request_id=utils.shortuuid(),
                frame=frame,
                is_final=True,
            )
        )


# ============================================================
# ElevenLabs TTS — High-quality cloned voice via API
# Cost control: short text → Piper (free), long → ElevenLabs
# Error fallback: ElevenLabs failure → Piper
# ============================================================

logger_el = logging.getLogger("elevenlabs-tts")


class ElevenLabsTTS(tts.TTS):
    """LiveKit-compatible TTS using ElevenLabs API with Piper fallback."""

    SAMPLE_RATE = 24000
    API_BASE = "https://api.elevenlabs.io/v1"

    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str,
        piper_fallback: PiperTTS,
        model_id: str = "eleven_multilingual_v2",
        char_threshold: int = 20,
    ):
        self._api_key = api_key
        self._voice_id = voice_id
        self._piper = piper_fallback
        self._model_id = model_id
        self._char_threshold = char_threshold
        self._voice_settings = {
            "stability": 0.4,
            "similarity_boost": 0.85,
            "style": 0.6,
            "use_speaker_boost": True,
        }

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=self.SAMPLE_RATE,
            num_channels=1,
        )
        logger_el.info(
            f"ElevenLabs TTS ready: voice_id={voice_id}, model={model_id}, "
            f"piper_fallback=yes, char_threshold={char_threshold}"
        )

    def update_voice_id(self, voice_id: str):
        """Update voice_id for session-specific cloned voices."""
        self._voice_id = voice_id
        logger_el.info(f"ElevenLabs voice_id updated: {voice_id}")

    def synthesize(
        self,
        text: str,
        *,
        conn_options: Optional[APIConnectOptions] = None,
    ) -> tts.ChunkedStream:
        text_stripped = text.strip()
        if len(text_stripped) < self._char_threshold:
            logger_el.debug(f"Cost control: {len(text_stripped)} chars → Piper (free)")
            return self._piper.synthesize(text, conn_options=conn_options)

        return ElevenLabsChunkedStream(
            tts=self,
            input_text=text,
            api_key=self._api_key,
            voice_id=self._voice_id,
            model_id=self._model_id,
            voice_settings=self._voice_settings,
            piper_fallback=self._piper,
        )


class ElevenLabsChunkedStream(tts.ChunkedStream):
    """Streams audio from ElevenLabs API with Piper fallback on error."""

    def __init__(
        self,
        *,
        tts: ElevenLabsTTS,
        input_text: str,
        api_key: str,
        voice_id: str,
        model_id: str,
        voice_settings: dict,
        piper_fallback: PiperTTS,
    ):
        super().__init__(tts=tts, input_text=input_text)
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._voice_settings = voice_settings
        self._piper = piper_fallback

    async def _run(self) -> None:
        try:
            await self._stream_elevenlabs()
        except Exception as e:
            logger_el.error(f"ELEVENLABS_ERROR_FALLBACK: {e}")
            await self._fallback_piper()

    async def _stream_elevenlabs(self) -> None:
        """Stream audio from ElevenLabs text-to-speech API."""
        url = f"{ElevenLabsTTS.API_BASE}/text-to-speech/{self._voice_id}/stream"
        headers = {"xi-api-key": self._api_key, "Content-Type": "application/json"}
        body = {
            "text": self._input_text,
            "model_id": self._model_id,
            "voice_settings": self._voice_settings,
        }

        request_id = utils.shortuuid()
        has_sent = False
        # ~0.5s chunks: 24000 Hz × 2 bytes × 0.5s = 24000 bytes
        chunk_bytes = 24000

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=body,
                params={"output_format": "pcm_24000"},
                timeout=30.0,
            ) as resp:
                resp.raise_for_status()
                buffer = bytearray()

                async for data in resp.aiter_bytes(4096):
                    buffer.extend(data)

                    while len(buffer) >= chunk_bytes:
                        chunk_data = bytes(buffer[:chunk_bytes])
                        buffer = buffer[chunk_bytes:]
                        samples = len(chunk_data) // 2

                        frame = rtc.AudioFrame(
                            data=chunk_data,
                            sample_rate=ElevenLabsTTS.SAMPLE_RATE,
                            num_channels=1,
                            samples_per_channel=samples,
                        )
                        self._event_ch.send_nowait(
                            tts.SynthesizedAudio(
                                request_id=request_id,
                                frame=frame,
                            )
                        )
                        has_sent = True

                # Flush remaining buffer
                if buffer:
                    remaining = bytes(buffer)
                    samples = len(remaining) // 2
                    if samples > 0:
                        frame = rtc.AudioFrame(
                            data=remaining,
                            sample_rate=ElevenLabsTTS.SAMPLE_RATE,
                            num_channels=1,
                            samples_per_channel=samples,
                        )
                        self._event_ch.send_nowait(
                            tts.SynthesizedAudio(
                                request_id=request_id,
                                frame=frame,
                                is_final=True,
                            )
                        )
                        has_sent = True

        if not has_sent:
            raise RuntimeError("ElevenLabs returned empty audio response")

    async def _fallback_piper(self) -> None:
        """Synthesize using Piper as fallback when ElevenLabs fails."""

        def _synthesize():
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                self._piper._voice.synthesize(self._input_text, wf)
            buf.seek(0)
            with wave.open(buf, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                pcm = wf.readframes(n_frames)
            return pcm, sample_rate, n_frames

        pcm, sample_rate, samples = await asyncio.get_event_loop().run_in_executor(
            None, _synthesize
        )

        frame = rtc.AudioFrame(
            data=pcm,
            sample_rate=sample_rate,
            num_channels=1,
            samples_per_channel=samples,
        )

        self._event_ch.send_nowait(
            tts.SynthesizedAudio(
                request_id=utils.shortuuid(),
                frame=frame,
                is_final=True,
            )
        )
