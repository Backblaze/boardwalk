"""
Common application exception classes
"""

import typing

from click import ClickException
from loguru import logger


class BoardwalkException(ClickException):
    """
    click will handle subclasses of ClickException specially. We override the
    show method to make log formatting consistent
    """

    def show(self, file: typing.IO[str] | None = None) -> None:
        logger.error(self.format_message())
