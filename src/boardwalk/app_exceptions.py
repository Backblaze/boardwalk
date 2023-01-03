"""
Common application exception classes
"""
import typing

from click import ClickException

from boardwalk.log import boardwalk_logger


class BoardwalkException(ClickException):
    """
    click will handle subclasses of ClickException specially. We override the
    show method to make log formatting consistent
    """

    def show(self, file: typing.IO[str] | None = None) -> None:

        boardwalk_logger.error(self.format_message())
