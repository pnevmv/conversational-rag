import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class ExperimentLogger:
    """Simple JSONL logger for experiment runs."""

    def __init__(self, experiment_name: str, log_dir: Optional[Path] = None):
        self.experiment_name = experiment_name
        project_root = Path(__file__).resolve().parent.parent.parent
        self.log_dir = log_dir or (project_root / "experiments" / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{experiment_name}.jsonl"

    def log(
        self,
        question: str,
        answer: str,
        model: str,
        prompt: Optional[str] = None,
        context: Optional[str] = None,
        dataset: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an experiment interaction entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_name": self.experiment_name,
            "model": model,
            "question": question,
            "prompt": prompt or question,
            "context": context,
            "answer": answer,
            "dataset": dataset,
            "metadata": metadata or {},
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry
