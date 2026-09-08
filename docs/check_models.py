"""Send one real request per candidate model id and report what works.

Run this the morning of the talk. Listing models is not enough: an id can appear
in models.list() and still return 404 on generation.

    python3 docs/check_models.py
"""

from __future__ import annotations

from dotenv import load_dotenv
from google import genai
from google.genai import types

CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

_DECLARATION = types.FunctionDeclaration(
    name="get_flights",
    description="Find flights between two airports.",
    parameters_json_schema={
        "type": "object",
        "properties": {"origin": {"type": "string"}, "dest": {"type": "string"}},
        "required": ["origin", "dest"],
    },
)


def main() -> None:
    load_dotenv()
    client = genai.Client()
    tools = [types.Tool(function_declarations=[_DECLARATION])]

    for model in CANDIDATES:
        try:
            response = client.models.generate_content(
                model=model,
                contents="Find flights from CMB to SIN",
                config=types.GenerateContentConfig(tools=tools),
            )
            parts = response.candidates[0].content.parts or []
            calls = [p.function_call.name for p in parts if p.function_call]
            verdict = f"OK, tool call {calls}" if calls else "OK, but no tool call"
        except Exception as exc:  # noqa: BLE001 - we want every failure reported
            verdict = f"FAIL {str(exc)[:80]}"
        print(f"{model:24} {verdict}")


if __name__ == "__main__":
    main()
