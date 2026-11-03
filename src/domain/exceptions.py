from __future__ import annotations


class LlmError(Exception):
    def __init__(self, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.retryable = retryable


class LlmUnavailableError(LlmError): ...


class LlmFailedError(LlmError): ...


class NotEnoughDataError(Exception):
    def __init__(self, missing_fields: tuple[str, ...]) -> None:
        super().__init__("мало данных")
        self.missing_fields = missing_fields
