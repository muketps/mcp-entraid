from __future__ import annotations

import secrets
import string
from dataclasses import dataclass

from mcp_entraid.schemas.passwords import GeneratedPasswordMetadata

SYMBOLS = "@#$%&*!?+-_="
FORBIDDEN_PATTERNS = ("123", "1234", "abc", "qwerty", "password", "senha", "admin", "welcome")


@dataclass
class PasswordResetService:
    def generate_temporary_password(self) -> tuple[str, GeneratedPasswordMetadata]:
        for _ in range(100):
            letters = [
                secrets.choice(string.ascii_uppercase),
                secrets.choice(string.ascii_lowercase),
            ]
            letters.extend(secrets.choice(string.ascii_letters) for _ in range(3))
            numbers = [secrets.choice(string.digits) for _ in range(3)]
            symbols = [secrets.choice(SYMBOLS) for _ in range(4)]
            characters = letters + numbers + symbols
            secrets.SystemRandom().shuffle(characters)
            password = "".join(characters)
            metadata = self._password_metadata(password)
            if self._is_locally_valid(password, metadata):
                return password, metadata
        raise RuntimeError("Nao foi possivel gerar senha temporaria valida localmente.")

    def _password_metadata(self, password: str) -> GeneratedPasswordMetadata:
        return GeneratedPasswordMetadata(
            length=len(password),
            letters_count=sum(character.isalpha() for character in password),
            numbers_count=sum(character.isdigit() for character in password),
            symbols_count=sum(character in SYMBOLS for character in password),
            has_lowercase=any(character.islower() for character in password),
            has_uppercase=any(character.isupper() for character in password),
            has_number=any(character.isdigit() for character in password),
            has_symbol=any(character in SYMBOLS for character in password),
        )

    def _is_locally_valid(self, password: str, metadata: GeneratedPasswordMetadata) -> bool:
        lowered = password.lower()
        return (
            metadata.length == 12
            and metadata.letters_count == 5
            and metadata.numbers_count == 3
            and metadata.symbols_count == 4
            and metadata.has_lowercase
            and metadata.has_uppercase
            and metadata.has_number
            and metadata.has_symbol
            and not any(pattern in lowered for pattern in FORBIDDEN_PATTERNS)
        )
