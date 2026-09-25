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


def test_the_readme_matrix_network_column_matches_each_tool():
    """Mentioning every tool was not enough: batch_process sat in the matrix
    with Network "no" while it could download rembg weights. Each row's
    Network cell is now checked against that tool's declared need."""
    from mini_creative_toolkit.capabilities import CAPABILITIES, NetworkNeed

    rows = {}
    for line in _read(REPO_ROOT / "README.md").splitlines():
        match = re.match(r"\| `(\w+)` \| [^|]+ \| ([^|]+) \|", line)
        if match and match.group(1) in CAPABILITIES:
            rows[match.group(1)] = match.group(2).strip().strip("*")
    assert set(rows) == set(CAPABILITIES)
    expected = {
        NetworkNeed.NONE: "no",
        NetworkNeed.FIRST_RUN_ONLY: "first run only",
        NetworkNeed.REQUIRED: "required",
    }
    for name, cell in rows.items():
        assert cell.startswith(expected[CAPABILITIES[name].network]), (name, cell)


def test_server_json_fits_the_mcp_registry_schema_limits():
    """The registry's server.schema.json (2025-12-11) caps ``description`` at
    100 characters; the 251-character one this file used to carry would have
    been rejected on publish. Checked here without fetching the schema."""
    import json

    server = json.loads(_read(REPO_ROOT / "server.json"))
    assert 1 <= len(server["description"]) <= 100, len(server["description"])
    assert server["name"].startswith("io.github.Furkiozknn/")
    readme = _read(REPO_ROOT / "README.md")
    assert f"<!-- mcp-name: {server['name']} -->" in readme
    import tomllib

    version = tomllib.loads(_read(REPO_ROOT / "pyproject.toml"))["project"]["version"]
    assert server["version"] == version
    assert all(p["version"] == version for p in server["packages"])


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


def test_the_registry_entry_can_actually_be_launched():
    """server.json tells MCP clients to run ``uvx <identifier>``. uvx runs the
    console script *named* like the package, so without one the registry
    entry installs fine and then fails with "executable not provided"."""
    import json
    import tomllib

    server = json.loads(_read(REPO_ROOT / "server.json"))
    scripts = tomllib.loads(_read(REPO_ROOT / "pyproject.toml"))["project"]["scripts"]
    for package in server["packages"]:
        if package.get("runtimeHint") != "uvx":
            continue
        identifier = package["identifier"]
        assert scripts.get(identifier) == "mini_creative_toolkit.server:main", (
            f"`uvx {identifier}` needs a console script called {identifier!r} "
            f"that starts the stdio server; pyproject declares {sorted(scripts)}"
        )


def test_the_published_network_count_matches_the_capability_table():
    """"N of them report network: none" is repeated in server.json, the README
    and the project metadata. It is only true if N is what the table says -
    remove_background declares first-run-only, because rembg downloads its
    weights the first time a model is used."""
    import json

    from mini_creative_toolkit.capabilities import CAPABILITIES, NetworkNeed

    offline = sum(1 for c in CAPABILITIES.values() if c.network is NetworkNeed.NONE)
    total = len(CAPABILITIES)
    description = json.loads(_read(REPO_ROOT / "server.json"))["description"]
    assert f"{offline} never touch the network" in description, description
    assert f"{total} " in description, description
    readme = _read(REPO_ROOT / "README.md")
    assert f"on {offline} of its {total} tools" in readme
    summary = json.loads(_read(REPO_ROOT / "project-meta.json"))["summary"]
    assert f"{offline} of them report" in summary, summary


def test_readme_registration_commands_do_not_depend_on_the_current_directory():
    """`claude mcp add ... -- uv run --project /repo toolkit.py` was the
    documented command, and it only connected when Claude Code was started
    inside the repository: uv resolves a script *file* against the current
    directory. Whatever follows `uv run --project <path>` must be a console
    script the package declares."""
    import tomllib

    scripts = set(tomllib.loads(_read(REPO_ROOT / "pyproject.toml"))["project"]["scripts"])
    readme = _read(REPO_ROOT / "README.md").replace("\\\n", " ")
    commands = [line for line in readme.splitlines() if line.lstrip().startswith("claude mcp add")]
    assert commands, "README no longer shows a claude mcp add command"
    for command in commands:
        words = command.split()
        if "--project" in words:
            target = words[words.index("--project") + 2]
            assert target in scripts, command
        if "--from" in words:
            assert words[words.index("--from") + 2] in scripts, command
        assert not any(w.endswith(".py") for w in words), command
