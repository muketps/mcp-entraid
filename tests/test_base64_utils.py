from __future__ import annotations

import base64

import pytest

from mcp_entraid.utils.base64_utils import Base64OutputDecodeError, decode_base64_output


def test_decode_base64_output_returns_dict_for_json_payload():
    encoded = base64.b64encode(b'{"ok": true}').decode("ascii")

    assert decode_base64_output(encoded) == {"ok": True}


def test_decode_base64_output_returns_string_for_text_payload():
    encoded = base64.b64encode("feito".encode("utf-8")).decode("ascii")

    assert decode_base64_output(encoded) == "feito"


def test_decode_base64_output_rejects_invalid_base64():
    with pytest.raises(Base64OutputDecodeError):
        decode_base64_output("not-base64")
