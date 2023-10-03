"""
This type stub file was generated by pyright and then manually modified
"""

import sys

import dns.resolver

ALLOW_SMTPUTF8 = ...
CHECK_DELIVERABILITY = ...
TEST_ENVIRONMENT = ...
GLOBALLY_DELIVERABLE = ...
DEFAULT_TIMEOUT = ...
ATEXT = ...
DOT_ATOM_TEXT = ...
ATEXT_INTL = ...
DOT_ATOM_TEXT_INTL = ...
ATEXT_HOSTNAME = ...
EMAIL_MAX_LENGTH = ...
LOCAL_PART_MAX_LENGTH = ...
DOMAIN_MAX_LENGTH = ...
SPECIAL_USE_DOMAIN_NAMES = ...
if sys.version_info >= (3,):
    unicode_class = str
else: ...

class EmailNotValidError(ValueError):
    """Parent class of all exceptions raised by this module."""

    ...

class EmailSyntaxError(EmailNotValidError):
    """Exception raised when an email address fails validation because of its form."""

    ...

class EmailUndeliverableError(EmailNotValidError):
    """Exception raised when an email address fails validation because its domain name does not appear deliverable."""

    ...

class ValidatedEmail:
    """The validate_email function returns objects of this type holding the normalized form of the email address
    and other information."""

    original_email: str = ...
    email: str = ...
    local_part: str = ...
    domain: str = ...
    ascii_email: str = ...
    ascii_local_part: str = ...
    ascii_domain: str = ...
    smtputf8: str = ...
    mx: str = ...
    mx_fallback_type: str = ...
    def __init__(self, **kwargs) -> None: ...
    def __self__(self): ...
    def __repr__(self): ...
    def __getitem__(self, key): ...
    def __eq__(self, other) -> bool: ...
    def as_constructor(self): ...
    def as_dict(self): ...

def caching_resolver(*, timeout=..., cache=...): ...
def validate_email(
    email: str,
    *,
    allow_smtputf8: bool = ...,
    allow_empty_local: bool = ...,
    check_deliverability: bool = ...,
    test_environment: bool = ...,
    globally_deliverable: bool = ...,
    timeout: float = ...,
    dns_resolver: dns.resolver.Resolver = ...,
) -> ValidatedEmail:
    """
    Validates an email address, raising an EmailNotValidError if the address is not valid or returning a dict of
    information when the address is valid. The email argument can be a str or a bytes instance,
    but if bytes it must be ASCII-only.
    """
    ...

def validate_email_local_part(local, allow_smtputf8=..., allow_empty_local=...): ...
def validate_email_domain_part(
    domain, test_environment=..., globally_deliverable=...
): ...
def validate_email_deliverability(
    domain, domain_i18n, timeout=..., dns_resolver=...
): ...
def main(): ...

if __name__ == "__main__": ...
