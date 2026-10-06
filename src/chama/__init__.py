"""Chama loan default prediction: data pipeline and MLOps."""


class StepFailed(RuntimeError):
    """A pipeline step stopped on purpose, with a message saying what to fix."""
