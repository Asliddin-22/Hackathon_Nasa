"""Reserved extension contract. There is deliberately no prediction implementation."""
from typing import Protocol

class PredictionProvider(Protocol):
    def forecast(self, historical_data: list[dict], context: dict) -> dict:
        """A future validated implementation must return uncertainty and model provenance."""
        ...
