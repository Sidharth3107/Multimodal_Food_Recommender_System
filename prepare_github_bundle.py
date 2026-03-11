from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "deploy" / "github_safe_bundle"

DIRECTORIES = [
    "nutriguard",
    "webapp",
    "tests",
    "examples/showcase_output",
]
FILES = [
    ".gitignore",
    ".dockerignore",
    ".gitattributes",
    "README.md",
    "PROJECT_REVIEW.md",
    "DEPLOYMENT.md",
    "requirements.txt",
    "Dockerfile",
    "render.yaml",
    "run_webapp.py",
    "main.py",
    "main.ipynb",
    "generate_showcase.py",
    "validate_examples.py",
    "prepare_space_bundle.py",
    "prepare_github_bundle.py",
    "examples/demo_cases.json",
    "examples/profile_alex.json",
    "data/input_images/pizza.jpg",
    "data/deploy_openfoodfacts.tsv",
    "tests/data/sample_openfoodfacts.tsv",
    "Food_Vision_Model/checkpoint-2400/config.json",
    "Food_Vision_Model/checkpoint-2400/preprocessor_config.json",
]
SKIP_DIR_NAMES = {"generated", "__pycache__", ".git", ".venv"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".pyd"}


def _copy_directory(relative_path: str) -> None:
    source = ROOT / relative_path
    target = OUTPUT / relative_path
    for item in source.rglob("*"):
        relative_item = item.relative_to(source)
        if any(part in SKIP_DIR_NAMES for part in relative_item.parts):
            continue
        if item.is_dir():
            continue
        if item.suffix.lower() in SKIP_SUFFIXES:
            continue
        destination = target / relative_item
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def _copy_file(relative_path: str) -> None:
    source = ROOT / relative_path
    destination = OUTPUT / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _normalize_dataset_path() -> None:
    source = OUTPUT / "data" / "deploy_openfoodfacts.tsv"
    target = OUTPUT / "data" / "raw" / "en.openfoodfacts.org.products.tsv"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _write_bundle_notes() -> None:
    note = OUTPUT / "GITHUB_BUNDLE_NOTES.md"
    note.write_text(
        "# GitHub-safe bundle\n\n"
        "This export excludes files that GitHub would reject on a normal public repository, including the 1 GB raw dataset and the 343 MB model weights file.\n\n"
        "The app still runs in a fallback mode using heuristic image recovery when the full checkpoint weights are not present.\n",
        encoding="utf-8",
    )


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for directory in DIRECTORIES:
        _copy_directory(directory)
    for file_path in FILES:
        _copy_file(file_path)

    _normalize_dataset_path()
    _write_bundle_notes()
    print(f"Created GitHub-safe bundle at {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

