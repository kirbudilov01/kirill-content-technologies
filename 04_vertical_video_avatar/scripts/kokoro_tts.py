#!/usr/bin/env python3
import argparse
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate local TTS with Kokoro ONNX.")
    parser.add_argument("--text-file", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--voice", default="af_sarah")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--lang", default="en-us")
    parser.add_argument("--model", default="research/avatar-lab/models/kokoro-v1.0.onnx")
    parser.add_argument("--voices", default="research/avatar-lab/models/voices-v1.0.bin")
    args = parser.parse_args()

    text = Path(args.text_file).read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("Text file is empty.")

    kokoro = Kokoro(args.model, args.voices)
    samples, sample_rate = kokoro.create(
        text,
        voice=args.voice,
        speed=args.speed,
        lang=args.lang,
    )
    sf.write(args.out, samples, sample_rate)
    print(f"Created: {args.out}")


if __name__ == "__main__":
    main()

