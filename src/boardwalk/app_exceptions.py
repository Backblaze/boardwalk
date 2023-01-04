"""
Common application exception classes
"""
import logging
import typing

from click import ClickException

logger = logging.getLogger(__name__)


class BoardwalkException(ClickException):
    """
    click will handle subclasses of ClickException specially. We override the
    show method to make log formatting consistent
    """

    def show(self, file: typing.IO[str] | None = None) -> None:

        logger.error(self.format_message())
