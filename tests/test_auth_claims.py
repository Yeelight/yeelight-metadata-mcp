import base64
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.auth import extract_token_claims


def fake_jwt(payload):
    def encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode(payload)}.signature"


def test_extract_token_claims_returns_only_supported_fields():
    token = fake_jwt({
        "region": "EU",
        "client_id": "iot-platform",
        "username": "must-not-leak",
    })

    claims = extract_token_claims(f"Bearer {token}")

    assert claims.region == "eu"
    assert claims.client_id == "iot-platform"
    assert not hasattr(claims, "username")


def test_extract_token_claims_tolerates_opaque_and_malformed_tokens():
    assert extract_token_claims("opaque-token").region is None
    assert extract_token_claims("broken.payload.signature").region is None
    assert extract_token_claims("").region is None


def test_extract_token_claims_rejects_invalid_claim_types_and_lengths():
    claims = extract_token_claims(fake_jwt({"region": ["cn"], "client_id": "x" * 300}))

    assert claims.region is None
    assert claims.client_id is None
