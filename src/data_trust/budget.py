"""Count SQL statements issued by a helper."""

from data_trust.errors import DataTrustError


class QueryBudget:
    """Hard stop after a fixed number of statements."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise DataTrustError("query budget must be at least 1")
        self.limit = limit
        self.used = 0

    def consume(self, count: int = 1) -> None:
        self.used += count
        if self.used > self.limit:
            raise DataTrustError(
                f"query budget exceeded: {self.used} statements used, limit is {self.limit}"
            )
