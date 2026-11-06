import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import compute, main

BACKENDS = compute.backend_status()


class TestSymPy(unittest.TestCase):
    def test_diff(self):
        out = compute.compute("x^2", "diff")
        self.assertEqual(out["backend"], "sympy")
        self.assertEqual(out["result"], "2*x")

    def test_forbidden(self):
        with self.assertRaises(compute.ComputeError):
            compute.compute("__import__('os')", "simplify")

    def test_backend_status(self):
        self.assertTrue(BACKENDS["sympy"]["available"])
        self.assertIn("diff", BACKENDS["sympy"]["operations"])

    def test_audit_sandbox_marker(self):
        out = compute.compute("x^2", "diff")
        self.assertEqual(out["sandbox"], "audit")
        self.assertEqual(out["credentials"]["sandbox"], "audit")


@unittest.skipUnless(BACKENDS["scipy"]["available"], "scipy not installed")
class TestSciPy(unittest.TestCase):
    def test_quad(self):
        out = compute.compute("x^2", "quad", point="0", target="1")
        self.assertEqual(out["backend"], "scipy")
        self.assertAlmostEqual(out["result"], 1 / 3, places=6)
        self.assertFalse(out["disputed"])
        self.assertIsNotNone(out["cross_check"])
        self.assertAlmostEqual(out["cross_check"]["value"], 1 / 3, places=6)

    def test_credentials(self):
        out = compute.compute("x^2", "diff")
        cred = out["credentials"]
        for key in ("backend", "engine_version", "input_sha256", "operation",
                    "assumptions", "verification", "disputed", "generated_at"):
            self.assertIn(key, cred)
        self.assertEqual(cred["backend"], "sympy")
        self.assertTrue(cred["verification"]["ok"])
        self.assertEqual(len(cred["input_sha256"]), 64)

    def test_timeout_kills_worker(self):
        with self.assertRaises(compute.ComputeError) as ctx:
            compute.compute("exp(x^2)*sin(x)^10", "integrate", timeout=0.1)
        self.assertIn("timed out", str(ctx.exception))

    def test_disputed_marker(self):
        fake = {"result": "1", "latex": "", "numeric": 1.0, "details": {},
                "disputed": True,
                "cross_check": {"backend": "sympy", "value": 2.0,
                                "difference": 1.0}}
        with mock.patch.object(compute, "_run_worker", return_value=fake):
            out = compute.compute("x", "diff")
        self.assertTrue(out["disputed"])
        self.assertTrue(out["credentials"]["disputed"])
        self.assertEqual(out["cross_check"]["difference"], 1.0)

    def test_minimize(self):
        out = compute.compute("(x-2)^2", "minimize", point="0")
        self.assertAlmostEqual(out["result"], 2.0, places=4)

    def test_root(self):
        out = compute.compute("x^2-2", "root", point="1", target="2")
        self.assertAlmostEqual(out["result"], 2 ** 0.5, places=4)


class TestOptionalBackends(unittest.TestCase):
    def test_pint_or_unavailable(self):
        if BACKENDS["pint"]["available"]:
            out = compute.compute("3 m", "convert", target="ft", backend="pint")
            self.assertAlmostEqual(out["numeric"], 9.8425, places=3)
        else:
            with self.assertRaises(compute.BackendUnavailable):
                compute.compute("3 m", "convert", target="ft", backend="pint")

    def test_control_or_unavailable(self):
        if BACKENDS["control"]["available"]:
            out = compute.compute(
                "", "step", backend="control",
                data={"num": [1], "den": [1, 2, 1]})
            self.assertTrue(out["ok"])
        else:
            with self.assertRaises(compute.BackendUnavailable):
                compute.compute("", "step", backend="control",
                                data={"num": [1], "den": [1, 2, 1]})

    def test_external_disabled(self):
        for backend in ("wolfram", "lean"):
            if not BACKENDS[backend]["available"]:
                with self.assertRaises(compute.BackendUnavailable):
                    compute.compute("1+1", "eval" if backend == "wolfram" else "check",
                                    backend=backend)

    def test_unknown_backend(self):
        with self.assertRaises(compute.ComputeError):
            compute.compute("x", "diff", backend="nope")


class TestAPI(unittest.TestCase):
    def test_backends_endpoint(self):
        r = TestClient(main.app).get("/v1/compute/backends")
        self.assertEqual(r.status_code, 200)
        self.assertIn("sympy", r.json()["backends"])

    def test_scipy_endpoint(self):
        if not BACKENDS["scipy"]["available"]:
            self.skipTest("scipy not installed")
        r = TestClient(main.app).post("/v1/compute", json={
            "expression": "x^2", "operation": "quad", "point": "0",
            "target": "1", "backend": "scipy"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["backend"], "scipy")

    def test_unavailable_is_503(self):
        backend = next((b for b in ("pint", "control", "wolfram", "lean")
                        if not BACKENDS[b]["available"]), None)
        if backend is None:
            self.skipTest("all optional backends installed")
        op = {"pint": "convert", "control": "step",
              "wolfram": "eval", "lean": "check"}[backend]
        r = TestClient(main.app).post("/v1/compute", json={
            "expression": "1", "operation": op, "backend": backend})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"]["code"], "backend_unavailable")


if __name__ == "__main__":
    unittest.main()
