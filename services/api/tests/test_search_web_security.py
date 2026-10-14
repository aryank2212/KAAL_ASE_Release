import socket
import unittest
from unittest.mock import Mock, patch

from app.search_web import _validate_public_http_url, fetch_page_text


class PublicURLValidationTests(unittest.TestCase):
    def test_blocks_local_and_private_addresses(self):
        for url in (
            "http://localhost/",
            "http://127.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://192.168.1.10/",
            "http://[::1]/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _validate_public_http_url(url)

    def test_blocks_non_http_schemes_credentials_and_unusual_ports(self):
        for url in (
            "file:///etc/passwd",
            "ftp://example.com/file",
            "https://user:password@example.com/",
            "https://example.com:8443/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _validate_public_http_url(url)

    @patch("app.search_web.socket.getaddrinfo")
    def test_blocks_hostname_resolving_to_private_address(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.10.20", 443))
        ]
        with self.assertRaises(ValueError):
            _validate_public_http_url("https://example.test/")

    @patch("app.search_web.socket.getaddrinfo")
    def test_accepts_hostname_resolving_only_to_public_address(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        self.assertEqual(
            _validate_public_http_url("https://example.com/"),
            "https://example.com/",
        )

    def test_redirect_to_loopback_is_rejected_before_second_request(self):
        redirect = Mock()
        redirect.status_code = 302
        redirect.headers = {"location": "http://127.0.0.1/admin"}
        redirect.close = Mock()

        def validate(url):
            if "127.0.0.1" in url:
                raise ValueError("Local addresses are blocked")
            return url

        with (
            patch("app.search_web._validate_public_http_url", side_effect=validate),
            patch("app.search_web.httpx.request", return_value=redirect) as request,
        ):
            self.assertIsNone(fetch_page_text("https://example.com/"))
            self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
