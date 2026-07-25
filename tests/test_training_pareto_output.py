import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.train_trainable_penguins import _training_pareto_output_path


def test_training_pareto_output_path_uses_artifacts_dir(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"

    expected_path = artifacts_dir / "trainable_penguin_pareto_front.pdf"

    assert _training_pareto_output_path(artifacts_dir) == expected_path
