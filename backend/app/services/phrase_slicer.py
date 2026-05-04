"""
Per-image phrase extraction from a paragraph audio.

Given an audio file for a paragraph and the number of images that paragraph
should produce, this module returns the EXACT words spoken during the time
window each image is supposed to cover. Used to give the LLM a tighter, more
specific prompt input than "the whole paragraph" — so the N generated images
visualize what's actually being SAID at each moment, not generic variations
of the paragraph theme.

Word-level transcription is cached on disk per paragraph (transcripts/pNNN.json)
so it only runs once per audio.
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple

from app.services.subtitle_engine import SubtitleEngine


def get_or_create_paragraph_words(
    audio_path: Path,
    cache_path: Path,
    subtitle_engine: SubtitleEngine,
) -> List[Dict]:
    """Returns word-level transcript for one paragraph audio file.

    Format per word: {"text": str, "start": ms, "end": ms, "confidence": float}.
    On cache miss, uploads to AssemblyAI and writes the JSON.
    """
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except Exception:
            pass
    words = subtitle_engine.transcribe_words(audio_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(words, indent=2), encoding="utf-8")
    return words


def slice_phrase_for_image(
    words: List[Dict],
    image_index: int,
    total_images: int,
    paragraph_duration_seconds: float,
) -> Tuple[str, float, float]:
    """Returns (phrase, time_start_seconds, time_end_seconds) for a 1-indexed image.

    The paragraph is split into `total_images` equal time windows; image i covers
    seconds [(i-1)·D/N, i·D/N). Words whose `start` (ms) falls in that window are
    concatenated into the phrase.
    """
    if total_images <= 0 or paragraph_duration_seconds <= 0:
        return ("", 0.0, 0.0)

    window = paragraph_duration_seconds / total_images
    t_start = (image_index - 1) * window
    t_end = image_index * window
    t_start_ms = t_start * 1000.0
    t_end_ms = t_end * 1000.0

    selected = [w["text"] for w in words if t_start_ms <= w["start"] < t_end_ms]
    phrase = " ".join(selected).strip()

    # Edge: last image absorbs any trailing words past the boundary so we don't
    # leave the final word(s) unassigned because of rounding.
    if image_index == total_images:
        trailing = [w["text"] for w in words if w["start"] >= t_end_ms]
        if trailing:
            phrase = (phrase + " " + " ".join(trailing)).strip()

    return (phrase, t_start, t_end)
