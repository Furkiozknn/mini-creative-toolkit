"""Static checks over the repository itself.

These encode the promises the README makes, so that breaking one of them
fails CI rather than quietly turning the documentation into a lie.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "src" / "mini_creative_toolkit"

PY_FILES = sorted(SOURCE.rglob("*.py")) + [REPO_ROOT / "toolkit.py"]
# This module itself is excluded from the scans below: it necessarily contains
# the very literals it searches for, so including it would always self-match.
ALL_PY = PY_FILES + [
    p for p in sorted((REPO_ROOT / "tests").glob("*.py")) if p.name != Path(__file__).name
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _calls(path: Path):
    """Every function call in a module, as AST nodes.

    Scanning the raw text would match this project's own prose - the ffmpeg
    engine's docstring explains *why* shell=True is never used, and a grep
    cannot tell that apart from a real call.
    """
    for node in ast.walk(ast.parse(_read(path), str(path))):
        if isinstance(node, ast.Call):
            yield node


def _call_name(node: ast.Call) -> str:
    target = node.func
    parts = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


def test_no_call_anywhere_passes_shell_true():
    """The whole subprocess design rests on argument lists. One shell=True
    would undo it, so it is checked structurally rather than assumed."""
    offenders = []
    for path in ALL_PY:
        for call in _calls(path):
            for keyword in call.keywords:
                if keyword.arg == "shell" and getattr(keyword.value, "value", None) is True:
                    offenders.append(f"{path.name}:{call.lineno}")
    assert offenders == [], f"shell=True found at: {offenders}"


def test_no_os_system_or_popen():
    offenders = [
        f"{path.name}:{call.lineno}"
        for path in ALL_PY
        for call in _calls(path)
        if _call_name(call) in {"os.system", "os.popen", "commands.getoutput"}
    ]
    assert offenders == [], offenders


def test_every_subprocess_call_passes_a_list_not_a_string():
    """subprocess.run(f"...") - a formatted string - is the shape that turns a
    filename into syntax. There should be none."""
    launchers = {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_output"}
    offenders = []
    for path in ALL_PY:
        for call in _calls(path):
            if _call_name(call) not in launchers or not call.args:
                continue
            first = call.args[0]
            if not isinstance(first, (ast.List, ast.Name, ast.Starred)):
                offenders.append(f"{path.name}:{call.lineno}")
    assert offenders == [], f"string-command subprocess call at: {offenders}"


def test_no_developer_specific_paths_survive():
    """The old toolkit.py hardcoded a Windows path that only ever resolved on
    one person's machine. Environment variables are now the only mechanism."""
    patterns = [
        r"C:\\\\Users\\\\",
        r"/Users/[a-z]",
        r"/home/(?!user\b)[a-z]+/",
        r"Claude projeler",
        r"furki\\",
    ]
    for path in PY_FILES + [REPO_ROOT / "README.md", REPO_ROOT / "pyproject.toml"]:
        if not path.exists():
            continue
        text = _read(path)
        for pattern in patterns:
            assert not re.search(pattern, text), f"{pattern!r} appears in {path.name}"


def test_upscayl_locations_come_only_from_the_environment():
    text = _read(SOURCE / "engines" / "upscayl.py")
    assert "upscayl-bin.exe" not in text
    config = _read(SOURCE / "config.py")
    assert "UPSCAYL_BIN_PATH" in config and "UPSCAYL_MODELS_PATH" in config


def test_the_only_outbound_url_lives_in_the_hosted_engine():
    """'Everything is local except one tool' is the project's central claim.
    A second http:// in another module would silently make it false."""
    url = re.compile(r"https?://(?!(?:localhost|127\.0\.0\.1|github\.com|arxiv\.org|creativecommons\.org|www\.apache\.org))")
    offenders = []
    for path in PY_FILES:
        if path.name == "pollinations.py":
            continue
        for line in _read(path).splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"'):
                continue  # comments and docstrings may cite sources
            if url.search(line):
                offenders.append(f"{path.name}: {stripped}")
    assert offenders == [], offenders


def test_only_the_hosted_engine_imports_an_http_client():
    for path in PY_FILES:
        text = _read(path)
        if path.name == "pollinations.py":
            continue
        assert not re.search(r"^\s*import httpx", text, re.M), path
        assert not re.search(r"^\s*import (requests|urllib\.request)", text, re.M), path


def test_no_secret_shaped_values_are_logged():
    """Nothing here handles credentials, and nothing should start to by
    accident - an f-string over os.environ in a log call would do it."""
    pattern = re.compile(r"logger\.\w+\([^)]*(os\.environ|getenv|token|secret|api_key|password)", re.I)
    offenders = [p for p in PY_FILES if pattern.search(_read(p))]
    assert offenders == [], offenders


def test_the_readme_capability_matrix_matches_the_declared_capabilities():
    """The matrix is documentation of a data structure. If they disagree, the
    documentation is wrong - so the disagreement should fail here."""
    from mini_creative_toolkit.capabilities import CAPABILITIES

    readme = _read(REPO_ROOT / "README.md")
    for name in CAPABILITIES:
        assert f"`{name}`" in readme, f"{name} is not mentioned in README.md"


def test_the_readme_discloses_the_hosted_tool_rather_than_claiming_to_be_offline():
    """Asserted positively on purpose. A blacklist of overclaim phrases matches
    the README's own *denial* of them ("there is no global 'CPU-only, no
    network' claim here"), which is the opposite of a problem. What actually
    matters is that the disclosure is present and specific."""
    readme = _read(REPO_ROOT / "README.md")
    assert "generate_image_free" in readme
    assert "Pollinations.ai" in readme
    lowered = readme.lower()
    assert "prompt is sent to a third party" in lowered
    assert "one tool" in lowered and "leaves" in lowered


def test_the_readme_never_says_every_tool_is_local():
    """These phrasings have no honest use in this README - unlike "no network",
    which appears inside a sentence explaining why no such claim is made."""
    lowered = _read(REPO_ROOT / "README.md").lower()
    for overclaim in (
        "all tools run locally",
        "every tool runs locally",
        "everything runs locally",
        "100% offline",
        "fully offline",
        "never makes network requests",
        "no network access",
    ):
        assert overclaim not in lowered, overclaim


def test_security_and_provenance_documents_exist_and_say_the_hard_part():
    security = _read(REPO_ROOT / "SECURITY.md")
    assert "not a sandbox" in security.lower()
    third_party = _read(REPO_ROOT / "THIRD_PARTY.md")
    assert "FSRCNN" in third_party
    assert "MIT" in third_party


def test_the_gitignore_still_keeps_generated_output_out_of_the_repo():
    ignored = _read(REPO_ROOT / ".gitignore")
    assert "output/" in ignored


def test_the_bundled_model_weights_ship_inside_the_package():
    """Outside the package they would be missing from an installed wheel, and
    upscale_image_fast would fail only for users who installed properly."""
    weights = sorted((SOURCE / "models").glob("FSRCNN_x*.pb"))
    assert [p.name for p in weights] == ["FSRCNN_x2.pb", "FSRCNN_x3.pb", "FSRCNN_x4.pb"]


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_every_module_compiles(path):
    compile(_read(path), str(path), "exec")
