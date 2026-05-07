from __future__ import annotations

import base64
import json
from binascii import Error as Base64DecodeError
from typing import Any


class Base64OutputDecodeError(ValueError):
    """Erro ao decodificar output base64 retornado pelo runbook."""


def decode_base64_output(value: str) -> str | dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise Base64OutputDecodeError("Output do runbook deve ser uma string base64 nao vazia.")

    try:
        decoded_bytes = base64.b64decode(value.strip(), validate=True)
        decoded_text = decoded_bytes.decode("utf-8")
    except (Base64DecodeError, UnicodeDecodeError, ValueError) as exc:
        raise Base64OutputDecodeError("Output do runbook nao e um base64 UTF-8 valido.") from exc

    stripped = decoded_text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return decoded_text
        if isinstance(payload, dict):
            return payload
        return {"value": payload}

    return decoded_text
