import json
import os
import shutil
import subprocess
import sys
import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tmp import mkdtemp  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable


class TestSandboxPolicy(unittest.TestCase):
    def test_network_and_writes_are_denied(self):
        tmp = mkdtemp(prefix="policy-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        outside = os.path.join(os.path.dirname(tmp), "policy-denied.txt")
        script = os.path.join(tmp, "probe.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(
                "import json, os, socket, subprocess, sys\n"
                "from app.sandbox_policy import install\n"
                "temp = sys.argv[1]\n"
                "install(temp)\n"
                "res = {}\n"
                "try:\n"
                "    socket.socket(); res['net'] = 'allowed'\n"
                "except PermissionError:\n"
                "    res['net'] = 'blocked'\n"
                "try:\n"
                "    open(os.path.join(os.path.dirname(temp), 'policy-denied.txt'),"
                " 'w').write('x'); res['fs'] = 'allowed'\n"
                "except PermissionError:\n"
                "    res['fs'] = 'blocked'\n"
                "try:\n"
                "    open(os.path.join(temp, 'ok.txt'), 'w').write('x');"
                " res['temp'] = 'allowed'\n"
                "except Exception as e:\n"
                "    res['temp'] = str(e)\n"
                "try:\n"
                "    subprocess.Popen([sys.executable, '-c', 'pass']);"
                " res['proc'] = 'allowed'\n"
                "except PermissionError:\n"
                "    res['proc'] = 'blocked'\n"
                "with open(os.path.join(temp, 'result.json'), 'w') as fh:\n"
                "    json.dump(res, fh)\n")
        env = os.environ.copy()
        env["PYTHONPATH"] = HERE + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run([PYTHON, script, tmp], env=env,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=30)
        self.assertEqual(proc.returncode, 0)
        with open(os.path.join(tmp, "result.json"), encoding="utf-8") as fh:
            res = json.load(fh)
        self.assertEqual(res["net"], "blocked")
        self.assertEqual(res["fs"], "blocked")
        self.assertEqual(res["temp"], "allowed")
        self.assertEqual(res["proc"], "blocked")


if __name__ == "__main__":
    unittest.main()
