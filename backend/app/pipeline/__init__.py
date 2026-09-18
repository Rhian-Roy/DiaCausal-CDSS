"""The message pipeline: six stages, one file each, run in order by runner.py."""

from app.pipeline.runner import STAGE_ORDER, run_pipeline

__all__ = ["STAGE_ORDER", "run_pipeline"]
