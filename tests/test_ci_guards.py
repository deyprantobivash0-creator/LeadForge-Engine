"""Exercise CI failure behavior in fresh subprocesses, without external AI."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("provider", ["gemini", "ollama"])
def test_ci_blocks_provider_even_with_synthetic_credentials(provider):
    env = os.environ.copy()
    env.update(LEADFORGE_CI="1", AI_PROVIDER="mock", ENVIRONMENT="test",
               DATABASE_URL="sqlite:///:memory:", GEMINI_API_KEY="synthetic-ci-key",
               OLLAMA_HOST="http://127.0.0.1:1", OLLAMA_MODEL="synthetic-ci-model")
    env.pop("LEADFORGE_ENV_FILE", None)
    class_name = {"gemini": "GeminiProvider", "ollama": "OllamaProvider"}[provider]
    code = f'''
import asyncio
from backend.ai.providers.{provider}_provider import {class_name}
from backend.ai.providers.base import ProviderNotConfigured
try:
    asyncio.run({class_name}().generate("synthetic prompt"))
except ProviderNotConfigured as exc:
    assert str(exc) == "Real AI providers are forbidden in CI"
else:
    raise AssertionError("CI provider guard did not fail closed")
'''
    result = subprocess.run([sys.executable, "-B", "-c", code], env=env,
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("required,expected", [("1", 1), ("0", 0)])
def test_postgres_skip_guard(tmp_path, required, expected):
    sample = tmp_path / "test_skip.py"
    sample.write_text("import pytest\n@pytest.mark.skip(reason='guard probe')\ndef test_skip(): pass\n")
    env = os.environ.copy()
    env.update(AI_PROVIDER="mock", LEADFORGE_REQUIRE_NO_SKIPS=required)
    result = subprocess.run([sys.executable, "-B", "-m", "pytest", "-p",
                             "scripts.ci_pytest", "-q", str(sample)], cwd=ROOT,
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == expected, result.stdout + result.stderr
