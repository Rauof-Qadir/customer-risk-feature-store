
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def run_step(description: str, command: list[str]) -> None:
    print(f"\n{'=' * 60}", flush=True)
    print(f"STEP: {description}", flush=True)
    print(f"{'=' * 60}", flush=True)

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
    )


def main() -> None:
    run_step(
        "Build customer features",
        [
            sys.executable,
            "-m",
            "src.feature_store.build_features",
        ],
    )

    run_step(
        "Validate feature dataset",
        [
            sys.executable,
            "-m",
            "src.feature_store.validate_feature_dataset",
        ],
    )

    run_step(
        "Run complete local test suite",
        [
            sys.executable,
            "-m",
            "pytest",
            "-v",
        ],
    )

    print("\nPIPELINE COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
