import click
from prompt_toolkit import print_formatted_text

from cli.utils import standard_error_handler


@click.command("install")
@click.pass_context
@standard_error_handler
def install(ctx):
    print_formatted_text("Installing Beiboot Operator...")


@click.command("uninstall")
@click.pass_context
@standard_error_handler
def uninstall(ctx):
    print_formatted_text("Removing Beiboot Operator...")
