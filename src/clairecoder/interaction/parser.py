from typing import Optional
import shlex
from .types import CommandRequest

class CommandParser:
    """Parses explicit commands according to CC-PRD-005 §9, §13.

    Commands follow: /COMMAND [SUBCOMMAND] [ARGUMENTS] [OPTIONS]
    The parser SHALL distinguish explicit Commands from ordinary user requests.
    Invalid/malformed commands SHALL NOT be silently treated as natural language.
    """

    @staticmethod
    def is_command(user_input: str) -> bool:
        """Determines if the input is an explicit command (starts with /)."""
        return user_input.strip().startswith("/")

    @staticmethod
    def parse(user_input: str) -> Optional[CommandRequest]:
        """Parses a command string into a CommandRequest.

        Returns None only for non-command input (no / prefix).
        Malformed commands (bare /) still produce a CommandRequest so the
        controller can generate a proper error per PRD §13.
        """
        text = user_input.strip()
        if not text.startswith("/"):
            return None

        body = text[1:]

        # Handle bare "/" — malformed but still a command attempt
        if not body.strip():
            return CommandRequest(
                command="",
                arguments={},
                raw_input=user_input
            )

        # Use shlex to handle quoted arguments
        try:
            parts = shlex.split(body)
        except ValueError:
            # Malformed quoting — still return a request so the controller
            # can produce a clear error rather than silently dropping input.
            parts = body.split()

        if not parts:
            return CommandRequest(
                command="",
                arguments={},
                raw_input=user_input
            )

        cmd_name = parts[0].lower()
        args_list = parts[1:]

        arguments = {}
        # Simple positional argument parsing for V1
        if args_list:
            arguments["args"] = args_list

        return CommandRequest(
            command=cmd_name,
            arguments=arguments,
            raw_input=user_input
        )
