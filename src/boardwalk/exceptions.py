import typing

from click import ClickException

from boardwalk.log import boardwalk_logger


class BoardwalkException(ClickException):
    def show(self, file: typing.IO[str] | None = None) -> None:

        boardwalk_logger.error(self.format_message())
