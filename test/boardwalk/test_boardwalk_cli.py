from importlib.metadata import version as lib_version

from click.testing import CliRunner

from boardwalk import cli


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli=cli.version)
    assert result.output.strip() == lib_version("boardwalk")
