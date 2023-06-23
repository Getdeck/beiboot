import logging
import sys
from pathlib import Path
from .utils import AliasedGroup

import click
from prompt_toolkit import print_formatted_text

from beiboot.configuration import ClientConfiguration


@click.group(cls=AliasedGroup)
@click.option(
    "--kubeconfig",
    help="Path to the kubeconfig file to use instead of loading the default",
)
@click.option(
    "--context",
    help="Context of the kubeconfig file to use instead of 'default'",
)
@click.option("-d", "--debug", default=False, is_flag=True)
@click.pass_context
def cli(ctx, kubeconfig, context, debug):
    import kubernetes as k8s

    ctx.ensure_object(dict)

    try:
        k8s.config.load_kube_config(config_file=kubeconfig, context=context)
    except k8s.config.ConfigException as e:
        raise RuntimeError(f"Could not load KUBECONFIG: {e}")

    ctx.obj["config"] = ClientConfiguration(
        getdeck_config_root=Path.home().joinpath(".getdeck")
    )
    if debug:
        console = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        console.setFormatter(formatter)

        logger = logging.getLogger("beiboot")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(console)


@cli.group("cluster", cls=AliasedGroup, help="Manage Beiboot clusters")
@click.pass_context
def cluster(ctx):
    pass


@cli.group("shelf", cls=AliasedGroup, help="Shelve Beiboot clusters")
@click.pass_context
def shelf(ctx):
    pass


@cli.command()
@click.pass_context
def version(ctx):
    from beiboot.configuration import __VERSION__

    print_formatted_text("Beiboot version: " + __VERSION__)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()

from .cluster import *  # noqa
from .install import *  # noqa
from .connect import *  # noqa
from .shelf import *  # noqa
