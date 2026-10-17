class InvalidInput(Exception):
    pass


class ConfigError(Exception):
    pass


class BudgetDenied(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class SourceUnavailable(Exception):
    pass
