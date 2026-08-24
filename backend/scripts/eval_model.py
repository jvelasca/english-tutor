"""Evaluación manual de un modelo LLM para el rol de tutor de inglés.

Envía un conjunto fijo de prompts de tutor al modelo indicado y muestra las
respuestas para que un humano compare calidad (correcciones, explicaciones, tono).

Uso:
    .venv\\Scripts\\python.exe scripts/eval_model.py --model llama3.1:8b

No depende de la red salvo Ollama local; no usa Whisper/Piper.
"""
from __future__ import annotations

import argparse
import sys

import ollama

# Windows: la consola por defecto usa cp1252 y falla al imprimir emojis/símbolos
# fonéticos (😊, θ). Forzamos UTF-8 para que el script no reviente en esos casos.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# (modo, system prompt, mensaje del alumno). Cubren los 4 modos del tutor (M4).
PROMPTS: list[tuple[str, str, str]] = [
    (
        "conversation",
        "You are a friendly, patient English tutor.",
        "Hi! I want to practice English. How was your day?",
    ),
    (
        "grammar",
        "You are an English grammar coach. Correct mistakes and explain briefly.",
        "I have 20 years old and I live in Madrid since 5 years.",
    ),
    (
        "exercises",
        "You are an English teacher who creates short, focused exercises.",
        "Give me a short fill-in-the-blank exercise about the past tense.",
    ),
    (
        "pronunciation",
        "You are an English pronunciation coach.",
        "How do I pronounce the word 'through' correctly?",
    ),
]


def eval_model(model: str) -> None:
    print(f"== Evaluando modelo: {model} ==\n")
    for mode, system, user in PROMPTS:
        print(f"--- [{mode}] {user}")
        try:
            resp = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                options={"temperature": 0.7},
            )
            content = resp.get("message", {}).get("content", "").strip()
            print(content)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {exc}")
        print("\n" + "-" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evalúa un modelo como tutor de inglés."
    )
    parser.add_argument("--model", required=True, help="Nombre del modelo en Ollama")
    args = parser.parse_args()
    eval_model(args.model)


if __name__ == "__main__":
    main()
