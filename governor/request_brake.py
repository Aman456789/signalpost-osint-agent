class RequestBrake:
    """Set the first time the brake denies a reservation. Nothing resets it within a run."""

    def __init__(self) -> None:
        self._tripped = False

    @property
    def tripped(self) -> bool:
        return self._tripped

    def trip(self) -> None:
        self._tripped = True
