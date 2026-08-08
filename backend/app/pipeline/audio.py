"""TTS voiceover + word-level timestamps."""

from pathlib import Path

from openai import OpenAI

from .. import config


def synthesize(script: str, voice_name: str, out_path: Path) -> None:
    openai_voice, instructions = config.VOICES.get(
        voice_name, config.VOICES[config.DEFAULT_VOICE]
    )
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    with client.audio.speech.with_streaming_response.create(
        model=config.TTS_MODEL,
        voice=openai_voice,
        input=script,
        instructions=instructions,
        response_format="mp3",
    ) as resp:
        resp.stream_to_file(out_path)


def word_timestamps(audio_path: Path) -> list[dict]:
    """Return [{"word": str, "start": float, "end": float}, ...]."""
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        tr = client.audio.transcriptions.create(
            model=config.TRANSCRIBE_MODEL,
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = [
        {"word": w.word.strip(), "start": float(w.start), "end": float(w.end)}
        for w in tr.words
        if w.word.strip()
    ]
    if not words:
        raise ValueError("transcription returned no word timestamps")
    return words
