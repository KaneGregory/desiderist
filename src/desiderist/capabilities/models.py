from enum import Enum


class ProviderStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REVOKED = "revoked"
