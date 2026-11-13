"""Portable tests of the public host-side pin/authentication boundary."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))
from nano_usb_client import NanoUSBClient, PinMismatch, AuthenticationError


class FakeResponse:
    def __init__(self, code, data):
        self.status = code
        self.data = data

    def read(self, limit):
        return self.data


class FakeSocket:
    def __init__(self, certificate_der):
        self.certificate_der = certificate_der

    def getpeercert(self, binary_form=False):
        assert binary_form is True
        return self.certificate_der


class FakeConnection:
    def __init__(self, cert, status=200):
        self.sock = FakeSocket(cert)
        self.status = status
        self.sent = []

    def connect(self):
        pass

    def request(self, *args, **kwargs):
        self.sent.append((args, kwargs))

    def getresponse(self):
        data = b'{"model_id":"qwen3.5-0.8b","status":"ready"}'
        return FakeResponse(self.status, data)

    def close(self):
        pass


class PublicClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "local-test-only")])
        cert = (x509.CertificateBuilder()
                .subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
                .sign(key, SHA256()))
        cls.cert_der = cert.public_bytes(Encoding.DER)
        spki = key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        cls.valid_pin = base64.b64encode(hashlib.sha256(spki).digest()).decode()

    def new_client(self, pin=None):
        return NanoUSBClient("https://127.0.0.1:49443",
                             pin or self.valid_pin, "x" * 64)

    def test_valid_pin_allows_status(self):
        fake = FakeConnection(self.cert_der)
        with patch("nano_usb_client.http.client.HTTPSConnection", return_value=fake):
            response = self.new_client().status()
        self.assertEqual(response["status"], "ready")
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(fake.sent[0][0][0], "GET")

    def test_wrong_pin_blocks_all_http(self):
        fake = FakeConnection(self.cert_der)
        bad = base64.b64encode(bytes.fromhex("01" * 32)).decode()
        with patch("nano_usb_client.http.client.HTTPSConnection", return_value=fake):
            with self.assertRaises(PinMismatch):
                self.new_client(bad).status()
        self.assertEqual(fake.sent, [])

    def test_wrong_bearer_returns_auth_error(self):
        fake = FakeConnection(self.cert_der, status=401)
        with patch("nano_usb_client.http.client.HTTPSConnection", return_value=fake):
            with self.assertRaises(AuthenticationError):
                self.new_client().status()

    def test_generate_bounds_without_network(self):
        client = self.new_client()
        with self.assertRaises(ValueError):
            client.generate(" " * 3)
        with self.assertRaises(ValueError):
            client.generate("A" * 8193)
        with self.assertRaises(ValueError):
            client.generate("valid", 513)
        with self.assertRaises(ValueError):
            client.generate("valid", True)

    def test_reject_insecure_or_non_loopback_host(self):
        for address in ("http://127.0.0.1:49443",
                        "https://0.0.0.0:49443",
                        "https://192.168.1.10:49443",
                        "https://127.0.0.1:49444"):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    NanoUSBClient(address, self.valid_pin, "x" * 64)


if __name__ == "__main__":
    unittest.main()
