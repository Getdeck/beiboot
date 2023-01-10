import click

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText

from beiboot import api
from beiboot.connection.types import ConnectorType
from cli.console import info, styles
from cli.__main__ import cli as _cli
from cli.utils import standard_error_handler


@_cli.command("connect", help="Set up the tunnel connection to a Beiboot cluster")
@click.argument("name")
@click.option(
    "--connector",
    type=click.Choice(["ghostunnel_docker", "dummy_no_connect"], case_sensitive=False),
    default="ghostunnel_docker",
)
@click.option("--host", help="Override the connection endpoint")
@click.pass_context
@standard_error_handler
def connect(ctx, name, connector, host):
    beiboot = api.read(name=name)
    connector_type = ConnectorType(connector)
    info(f"Now connecting to Beiboot '{name}' using connector '{connector_type}'")

    formatted_ports = ", ".join(
        list(
            map(
                lambda p: f"127.0.0.1:{p.split(':')[0]} -> cluster:{p.split(':')[1]}",
                beiboot.parameters.ports,  # type: ignore
            )
        )
    )
    print_formatted_text(
        FormattedText(  # type: ignore
            [
                ("class:info", "Creating port-forwards for the following ports: "),
                ("class:italic", formatted_ports),
            ],
            style=styles,
        )
    )

    connector = api.connect(beiboot, connector_type, host, config=ctx.obj["config"])

    location = connector.save_kubeconfig_to_file(beiboot)
    info(f"The kubeconfig file is written to {location}")
    print_formatted_text(
        FormattedText(  # type: ignore
            [
                ("class:info", "You can now run "),
                ("class:italic", f"'kubectl --kubeconfig {location} ... '"),
                ("class:info", "to interact with the cluster"),
            ],
            style=styles,
        )
    )


@_cli.command(
    "disconnect", help="Remove the tunnel connection and files from this host"
)
@click.argument("name")
@click.pass_context
@standard_error_handler
def disconnect(ctx, name):
    info(f"Now disconnecting from Beiboot '{name}'")
    api.terminate(name, ConnectorType.GHOSTUNNEL_DOCKER, config=ctx.obj["config"])
