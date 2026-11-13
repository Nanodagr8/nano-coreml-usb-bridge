"""Reference USB-only pinned-HTTPS client for NANO CoreML on a physical iPhone.

Never send bearer credentials or prompts before checking the TLS SPKI pin.
"""
import argparse
import base64
import binascii
import hashlib
import hmac
import http.client
import json
import os
import ssl
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


class PinMismatch(Exception):
    pass


class AuthenticationError(Exception):
    pass


class TransportError(Exception):
    pass


class NanoUSBClient:
    def __init__(self, base_url: str, tls_spki_pin: str, bearer: str):
        parts = urlsplit(base_url.rstrip("/"))
        if parts.scheme != "https" or parts.hostname != "127.0.0.1" or parts.port != 49443:
            raise ValueError("Only HTTPS loopback port 49443 is accepted")
        if parts.path not in ("", "/v1") or parts.username or parts.password or parts.query:
            raise ValueError("Unexpected USB HTTPS URL component")
        if not isinstance(bearer, str) or not (32 <= len(bearer) <= 128):
            raise ValueError("Bearer must be 32..128 printable ASCII characters")
        if not all(33 <= ord(char) <= 126 for char in bearer):
            raise ValueError("Bearer must contain printable ASCII without whitespace")
        value = tls_spki_pin.removeprefix("sha256//").removeprefix("sha256/")
        try:
            pin = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Invalid SPKI pin base64") from exc
        if len(pin) != 32:
            raise ValueError("SPKI pin must be a 32-byte SHA-256 digest")
        self._pin = pin
        self._bearer = bearer

    def _request(self, path: str, payload: dict | None = None) -> dict:
        # TLS peer certificate is authenticated by a pre-HTTP public-key pin.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection("127.0.0.1", 49443,
                                           timeout=25, context=context)
        try:
            conn.connect()
            peer = conn.sock.getpeercert(binary_form=True)
            if not peer:
                raise PinMismatch("No TLS server certificate presented")
            certificate = x509.load_der_x509_certificate(peer)
            public_key = certificate.public_key().public_bytes(
                Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
            actual = hashlib.sha256(public_key).digest()
            if not hmac.compare_digest(actual, self._pin):
                raise PinMismatch("TLS SPKI mismatch; no HTTP request sent")
            # No credential or prompt exists in any previous network write.
            headers = {"Accept": "application/json",
                       "Authorization": "Bearer " + self._bearer}
            data = None
            if payload is not None:
                data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                headers["Content-Type"] = "application/json"
                if len(data) > 16384:
                    raise ValueError("Request exceeds device 16 KiB body limit")
            conn.request("POST" if data is not None else "GET",
                         "/v1/neural/" + path, body=data, headers=headers)
            response = conn.getresponse()
            if response.status in (401, 403):
                raise AuthenticationError("Device rejected bearer credentials")
            if response.status != 200:
                raise TransportError("Unexpected HTTP status " + str(response.status))
            result = response.read(1_048_577)
            if len(result) > 1_048_576:
                raise TransportError("Response exceeds 1 MiB")
            decoded = json.loads(result)
            if not isinstance(decoded, dict):
                raise TransportError("Expected JSON object")
            return decoded
        finally:
            conn.close()

    def status(self) -> dict:
        result = self._request("status")
        if (result.get("model_id") != "qwen3.5-0.8b"
                or result.get("status") not in ("ready", "unloaded")):
            raise TransportError("Unexpected model status response")
        return result

    def generate(self, prompt: str, max_tokens: int = 32) -> dict:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be nonempty text")
        if len(prompt.strip().encode("utf-8")) > 8192:
            raise ValueError("Prompt must be at most 8 KiB")
        if type(max_tokens) is not int or not 1 <= max_tokens <= 512:
            raise ValueError("max_tokens must be an integer from 1 to 512")
        result = self._request("generate", {
            "model": "qwen3.5-0.8b",
            "prompt": prompt.strip(),
            "max_tokens": max_tokens,
            "stream": False,
        })
        if (result.get("model_id") != "qwen3.5-0.8b"
                or not isinstance(result.get("text"), str)):
            raise TransportError("Unexpected generation response")
        return result


def main():
    parser = argparse.ArgumentParser(description="Pinned USB HTTPS client for NANO Core ML")
    parser.add_argument("command", choices=("status", "generate"))
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--max-tokens", type=int, default=32)
    args = parser.parse_args()
    client = NanoUSBClient(
        os.environ.get("NANO_USB_URL", "https://127.0.0.1:49443"),
        os.environ.get("NANO_USB_TLS_PIN", ""),
        os.environ.get("NANO_USB_BEARER", ""),
    )
    result = client.status() if args.command == "status" else client.generate(
        args.prompt or "", args.max_tokens)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
