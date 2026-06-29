from pathlib import Path


def test_project_structure_exists() -> None:
    root = Path(__file__).resolve().parents[1]

    expected_paths = [
        "app.py",
        "README.md",
        "requirements.txt",
        "pyproject.toml",
        "config/settings.example.yaml",
        "src/data",
        "src/pricing",
        "src/strategies",
        "src/backtest",
        "src/agent",
        "src/visualization",
        "src/utils",
    ]

    missing = [path for path in expected_paths if not (root / path).exists()]

    assert not missing, f"Missing expected project paths: {missing}"
