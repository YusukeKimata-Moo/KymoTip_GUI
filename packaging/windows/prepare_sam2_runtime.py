"""Prepare a privacy-checked Windows SAM2 runtime without editing its source env."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tokenize


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "packaging" / "envs" / "sam2"
DEFAULT_DESTINATION = PROJECT_ROOT / "build" / "windows-sam2-runtime"
PROFILE_PATH = re.compile(r"[A-Za-z]:[/\\]Users[/\\][^/\\]+", re.IGNORECASE)
PRIVATE_METADATA_FIELDS = {"extracted_package_dir", "package_tarball_full_path", "source"}


def development_only(name: str) -> bool:
    return (
        Path(name).suffix.lower() in {".pdb", ".pc", ".cmake"}
        or name == "c_rehash.pl"
        or name.endswith("Config.sh")
    )


def copy_ignore(directory: str, names: list[str]) -> set[str]:
    parent = Path(directory)
    ignored = set()
    for name in names:
        child = parent / name
        reparse_point = getattr(child.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        if child.is_symlink() or reparse_point:
            raise ValueError(f"Symlink is not allowed in the runtime: {child}")
        if name == "__pycache__" or development_only(name):
            ignored.add(name)
        elif child.suffix.lower() in {".pyc", ".pyo"} and child.with_suffix(".py").exists():
            ignored.add(name)
    return ignored


def clean_metadata(value):
    if isinstance(value, dict):
        return {
            key: clean_metadata(item)
            for key, item in value.items()
            if not (key in PRIVATE_METADATA_FIELDS and isinstance(item, str) and PROFILE_PATH.search(item))
        }
    if isinstance(value, list):
        return [clean_metadata(item) for item in value]
    if isinstance(value, str):
        # Other build provenance is diagnostic, not used by the Python worker.
        return "<build-path>" if PROFILE_PATH.search(value) else value
    return value


def redact_build_config(path: Path, source: Path) -> None:
    text = path.read_text(encoding="utf-8")
    tokens = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.STRING:
            try:
                value = ast.literal_eval(token.string)
            except (ValueError, SyntaxError):
                value = None
            if isinstance(value, str):
                cleaned = value
                for prefix in (str(source), source.as_posix()):
                    cleaned = cleaned.replace(prefix, "<SAM2_RUNTIME>")
                cleaned = PROFILE_PATH.sub("<build-user>", cleaned)
                if cleaned != value:
                    token = token._replace(string=repr(cleaned))
        tokens.append(token)
    text = tokenize.untokenize(tokens)
    ast.parse(text, filename=str(path))
    path.write_text(text, encoding="utf-8", newline="\n")


def audit_private_paths(destination: Path, forbidden_values: list[str]) -> None:
    needles = []
    for value in forbidden_values:
        if value:
            needles.extend((value.lower().encode("utf-8"), value.lower().encode("utf-16-le")))
    ripgrep = shutil.which("rg")
    if ripgrep and needles:
        # A byte-oriented search covers executables as well as text and UTF-16.
        command = [
            ripgrep, "--text", "--files-with-matches", "--null",
            "--ignore-case", "--no-ignore", "--hidden",
            "--encoding", "none", "--no-unicode",
        ]
        for needle in needles:
            command.extend(("-e", "".join(f"\\x{byte:02x}" for byte in needle)))
        command.append(str(destination))
        result = subprocess.run(command, capture_output=True)
        if result.returncode not in (0, 1):
            raise ValueError("Runtime audit failed: " + result.stderr.decode("utf-8", errors="replace"))
        if result.returncode == 0:
            findings = [
                str(Path(name).relative_to(destination))
                for name in result.stdout.decode("utf-8").split("\0") if name
            ]
            raise ValueError("Private build paths remain in: " + ", ".join(findings))
        return
    overlap = max(map(len, needles), default=1) - 1
    findings = []
    for directory, _, filenames in os.walk(destination):
        for filename in filenames:
            path = Path(directory) / filename
            tail = b""
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    block = tail + block.lower()
                    if any(needle in block for needle in needles):
                        findings.append(str(path.relative_to(destination)))
                        break
                    tail = block[-overlap:] if overlap else b""
    if findings:
        raise ValueError("Private build paths remain in: " + ", ".join(findings))


def prepare(source: Path, destination: Path) -> dict:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    build_root = (PROJECT_ROOT / "build").resolve()
    if (
        destination == source or source in destination.parents
        or build_root not in destination.parents
    ):
        raise ValueError("The destination must be a separate directory below this project's build directory")
    if destination == build_root or destination.exists():
        raise ValueError("Use a new destination; existing runtime files will not be deleted automatically")
    if not (source / "python.exe").is_file():
        raise ValueError("The source is not a Windows Python environment")

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = copy_ignore(directory, names)
        if Path(directory) == source:
            ignored.add("Scripts")
        return ignored

    shutil.copytree(source, destination, ignore=ignore)
    metadata_directory = destination / "conda-meta"
    history = metadata_directory / "history"
    history.unlink(missing_ok=True)
    for metadata_path in metadata_directory.glob("*.json"):
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata_path.write_text(json.dumps(clean_metadata(value), indent=2) + "\n", encoding="utf-8")
    for package in ("numpy", "scipy"):
        redact_build_config(destination / "Lib" / "site-packages" / package / "__config__.py", source)

    return validate_runtime(source, destination)


def validate_runtime(source: Path, destination: Path) -> dict:
    if (destination / "Scripts").exists() or (destination / "conda-meta" / "history").exists():
        raise ValueError("Local environment history or unused entry-point scripts remain")
    if any(destination.rglob("__pycache__")):
        raise ValueError("Python bytecode caches were created after runtime preparation")
    home_profile = os.environ.get("USERPROFILE", str(Path.home()))
    profile_match = PROFILE_PATH.search(str(source))
    profile_name = profile_match.group().replace("\\", "/").split("/")[-1] if profile_match else ""
    audit_private_paths(destination, [home_profile, str(source), source.as_posix(), profile_name])
    required = [
        "python.exe",
        "Lib/site-packages/torch/__init__.py",
        "Lib/site-packages/sam2/__init__.py",
        "sam2/weights/sam2_hiera_tiny.pt",
    ]
    for relative_path in required:
        runtime_file = destination / relative_path
        if not runtime_file.is_file():
            raise ValueError(f"Required runtime file missing: {relative_path}")
        original_file = source / relative_path
        if hashlib.sha256(runtime_file.read_bytes()).digest() != hashlib.sha256(original_file.read_bytes()).digest():
            raise ValueError(f"Required runtime file changed: {relative_path}")
    return {
        "private_path_audit": "passed", "required_files": "unchanged",
        "scripts": "excluded", "bytecode_cache": "excluded",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--audit-only", action="store_true",
        help="Recheck an already prepared runtime before distribution",
    )
    args = parser.parse_args()
    if args.audit_only:
        result = validate_runtime(
            args.source.resolve(strict=True), args.destination.resolve(strict=True),
        )
    else:
        result = prepare(args.source, args.destination)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
