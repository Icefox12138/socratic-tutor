import os
import sys
import unittest

from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config, main  # noqa: E402


class TestTokenGuard(unittest.TestCase):
    def setUp(self):
        self.old = config.TOKEN
        config.TOKEN = "s3cret"

    def tearDown(self):
        config.TOKEN = self.old

    def test_project_header(self):
        main.require_token(x_sidecar_token="s3cret")          # no raise

    def test_bearer(self):
        main.require_token(authorization="Bearer s3cret")

    def test_bearer_is_case_insensitive(self):
        main.require_token(authorization="bearer s3cret")

    def test_wrong_token_rejected(self):
        with self.assertRaises(HTTPException):
            main.require_token(x_sidecar_token="nope")
        with self.assertRaises(HTTPException):
            main.require_token(authorization="Bearer nope")

    def test_open_when_unconfigured(self):
        config.TOKEN = ""
        main.require_token()
