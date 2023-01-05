import click
from click import ClickException


def standard_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:  # noqa
            ce = ClickException(message=str(e))
            raise ce

    return wrapper


class AliasedCommand(click.Command):
    def __init__(
        self,
        name,
        alias=[],
        context_settings=None,
        callback=None,
        params=None,
        help=None,
        epilog=None,
        short_help=None,
        options_metavar="[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
    ) -> None:
        super().__init__(
            name,
            context_settings,
            callback,
            params,
            help,
            epilog,
            short_help,
            options_metavar,
            add_help_option,
            no_args_is_help,
            hidden,
            deprecated,
        )
        self.alias = alias


class AliasedGroup(click.Group):

    command_class = AliasedCommand

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        for _, cmd in self.commands.items():
            if hasattr(cmd, "alias") and cmd_name in cmd.alias:
                return cmd
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def format_commands(self, ctx, formatter) -> None:
        commands = []
        _run_commands = sorted(self.commands.items())
        for subcommand, acmd in _run_commands:
            cmd = self.get_command(ctx, subcommand)
            # What is this, the tool lied about a command.  Ignore it
            if cmd is None:
                continue
            if cmd.hidden:
                continue

            if hasattr(acmd, "alias"):
                alias = ",".join(acmd.alias)
            else:
                alias = None
            commands.append((f"{subcommand} {'('+alias+')' if alias else ''}", cmd))

        # allow for 3 times the default spacing
        if len(commands):
            limit = formatter.width - 6 - max(len(cmd[0]) for cmd in commands)

            rows = []
            for subcommand, cmd in commands:
                help = cmd.get_short_help_str(limit)
                rows.append((subcommand, help))

            if rows:
                with formatter.section("Commands"):
                    formatter.write_dl(rows)

    def resolve_command(self, ctx, args):
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name, cmd, args
