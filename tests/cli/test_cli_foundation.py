"""Tests for the CLI foundation."""
from clairecoder.cli.main import run_cli

def test_cli_entry_point():
    # Calling the CLI entry point directly with no args should return 0
    exit_code = run_cli([])
    assert exit_code == 0
