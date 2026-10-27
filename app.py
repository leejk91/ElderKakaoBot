"""Kakao i Open Builder skill server for the magic-resistance calculator."""

from __future__ import annotations

import json
import math
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def calculate(my_resistance: float, magic_pressure: float) -> dict[str, float]:
    """Calculate damage multipliers from resistance and magic pressure."""
    difference = my_resistance - magic_pressure

    if difference < 0:
        shortfall = -difference
        outgoing = 0.5 ** (shortfall / 1_000)
        incoming = 1 + (shortfall / 1_000) ** 0.75
    else:
        excess = difference
        outgoing = 1 + 0.5 * (1 - 0.5 ** (excess / 4_000))
        incoming = 1.0

    return {
        "difference": difference,
        "outgoing_multiplier": outgoing,
        "incoming_multiplier": incoming,
    }


def format_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def calculator_reply(utterance: str) -> str:
    # Accept either "!마도 3200 4000" or "!마도저항 3200 4000".
    match = re.fullmatch(
        r"\s*!마도(?:저항)?\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*",
        utterance,
    )
    if not match:
        return "사용법: !마도 <내 마도저항> <마도 압력>\n예: !마도 3200 4000"

    resistance, pressure = map(float, match.groups())
    if not (math.isfinite(resistance) and math.isfinite(pressure)):
        return "저항과 압력은 유효한 숫자로 입력해 주세요."

    result = calculate(resistance, pressure)
    difference = result["difference"]
    relation = "부족" if difference < 0 else "초과" if difference > 0 else "일치"
    return (
        f"내 마도저항: {format_number(resistance)}\n"
        f"마도 압력: {format_number(pressure)}\n"
        f"차이: {format_number(difference)} ({relation})\n"
        f"주는 피해: ×{result['outgoing_multiplier']:.4f}\n"
        f"받는 피해: ×{result['incoming_multiplier']:.4f}"
    )


def kakao_response(text: str) -> dict[str, Any]:
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
        },
    }


class SkillHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path not in ("/", "/healthz"):
            self.send_error(404)
            return

        body = b"Kakao magic calculator is running. POST /skill for the Kakao skill.\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.rstrip("/") != "/skill":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1_000_000:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            utterance = payload["userRequest"]["utterance"]
            if not isinstance(utterance, str):
                raise ValueError("utterance must be text")
            text = calculator_reply(utterance)
            response = kakao_response(text)
            encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            encoded = json.dumps(
                kakao_response("요청을 읽지 못했어요. !마도 <내 마도저항> <마도 압력> 형식으로 입력해 주세요."),
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    print(f"Kakao skill server listening on http://{host}:{port}/skill")
    ThreadingHTTPServer((host, port), SkillHandler).serve_forever()
