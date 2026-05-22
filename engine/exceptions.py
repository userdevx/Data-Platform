class EngineError(Exception):
    pass


class ValidationError(EngineError):
    pass


class RecordNotFoundError(EngineError):
    pass


class DuplicateRecordError(EngineError):
    pass
