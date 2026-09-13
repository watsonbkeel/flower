class DomainError(ValueError):
    def __init__(self, code, message=None, status=409, retryable=False):
        self.code, self.message = code, message or code
        self.status, self.retryable = status, retryable
        super().__init__(code)
