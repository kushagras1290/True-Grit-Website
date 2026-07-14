"""Unit tests for the Google ID token verifier.

A fixed RSA keypair (generated once, for tests only) signs Google-style ID
tokens and serves as the JWKS. This exercises the real RS256 verification and
claim checks with zero network access and no third-party crypto dependency.
"""

from __future__ import annotations

import base64
import hashlib
import json

import pytest

from truegrit_api.auth.google import (
    _SHA256_DIGEST_INFO_PREFIX,
    GoogleAuthError,
    GoogleTokenVerifier,
)

# Test-only 2048-bit RSA keypair. Never used for anything but signing fixtures.
N = 14815257507125186650652503916934592491075827059902404748993824065373612208404694877515584485951614175548819240991603069244485246011201302039588919063307069245827957212081834099002280760882978398885673707192901849359594937729855148934692054886675045267855473013481164388594082687137723611951203770101307199094412438311932149822480508154609944906269421932256224052755575516492280858562475160578085596343668901619991030732790578931608632092879544506359622290168278134264589462655517634108235003349118512198665226309000171636275455173055704876509513609671603354597175232616186366022625755127404908308467944761932664912617  # noqa: E501
E = 65537
D = 14512111798333895085604897103186491593406835740688386335450318594087681909924894217876778944110194601729282695190456545664570774569099574068594080415460894110276203384146442800548551440036066363960277542563064026755703749370672767154607186101057283763603002053396353648933972140676157056209766654339129300289138551162049966907124953517972919548309480438157913418496996138553494759720876291158841588278557293746321770274195378861342905343596531567327382718385243985013568317685191425794065019841380808651105985308330906611037107556228775184570670064940904521139325149092875433897451623201243235789531358446565904627201  # noqa: E501

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
KID = "test-key-1"
NOW = 1_800_000_000.0


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _int_to_b64url(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return _b64url(value.to_bytes(length, "big"))


def _sign(signing_input: bytes) -> bytes:
    k = (N.bit_length() + 7) // 8
    digest_info = _SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(signing_input).digest()
    padding_length = k - len(digest_info) - 3
    encoded_message = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    return pow(int.from_bytes(encoded_message, "big"), D, N).to_bytes(k, "big")


def make_token(claims: dict, *, kid: str = KID) -> str:
    header = _b64url(json.dumps({"alg": "RS256", "kid": kid, "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    signature = _b64url(_sign(f"{header}.{payload}".encode("ascii")))
    return f"{header}.{payload}.{signature}"


def default_claims(**overrides) -> dict:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-subject-123",
        "email": "leaf@example.com",
        "email_verified": True,
        "name": "Leaf Grower",
        "iat": NOW - 30,
        "exp": NOW + 3600,
    }
    claims.update(overrides)
    return claims


def build_verifier() -> GoogleTokenVerifier:
    jwk = {
        "kty": "RSA",
        "alg": "RS256",
        "kid": KID,
        "n": _int_to_b64url(N),
        "e": _int_to_b64url(E),
    }
    return GoogleTokenVerifier(jwks_fetcher=lambda: {"keys": [jwk]}, clock=lambda: NOW)


def test_valid_token_returns_identity():
    identity = build_verifier().verify(make_token(default_claims()), client_id=CLIENT_ID)
    assert identity.subject == "google-subject-123"
    assert identity.email == "leaf@example.com"
    assert identity.name == "Leaf Grower"
    assert identity.email_verified is True


def test_rejects_wrong_audience():
    token = make_token(default_claims(aud="someone-else"))
    with pytest.raises(GoogleAuthError, match="another app"):
        build_verifier().verify(token, client_id=CLIENT_ID)


def test_rejects_expired_token():
    token = make_token(default_claims(exp=NOW - 120))
    with pytest.raises(GoogleAuthError, match="expired"):
        build_verifier().verify(token, client_id=CLIENT_ID)


def test_rejects_bad_issuer():
    token = make_token(default_claims(iss="https://evil.example.com"))
    with pytest.raises(GoogleAuthError, match="issuer"):
        build_verifier().verify(token, client_id=CLIENT_ID)


def test_rejects_unverified_email():
    token = make_token(default_claims(email_verified=False))
    with pytest.raises(GoogleAuthError, match="not verified"):
        build_verifier().verify(token, client_id=CLIENT_ID)


def test_rejects_tampered_payload():
    token = make_token(default_claims())
    header, _, signature = token.split(".")
    forged_payload = _b64url(json.dumps(default_claims(email="attacker@evil.test")).encode())
    tampered = f"{header}.{forged_payload}.{signature}"
    with pytest.raises(GoogleAuthError, match="signature is invalid"):
        build_verifier().verify(tampered, client_id=CLIENT_ID)


def test_rejects_unknown_signing_key():
    token = make_token(default_claims(), kid="rotated-away")
    with pytest.raises(GoogleAuthError, match="unknown key"):
        build_verifier().verify(token, client_id=CLIENT_ID)


def test_rejects_when_not_configured():
    with pytest.raises(GoogleAuthError, match="not configured"):
        build_verifier().verify(make_token(default_claims()), client_id="")


@pytest.mark.parametrize("bad", ["", "only-one-part", "two.parts", "a.b.c.d"])
def test_rejects_malformed_token(bad: str):
    with pytest.raises(GoogleAuthError):
        build_verifier().verify(bad, client_id=CLIENT_ID)
