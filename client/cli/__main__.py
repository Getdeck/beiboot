import logging
import sys
from pathlib import Path

import click
from prompt_toolkit import print_formatted_text

from beiboot.configuration import ClientConfiguration

from cli.cluster import (
    create_cluster,
    delete_cluster,
    list_clusters,
    connect,
    inspect,
    disconnect,
)
from cli.install import install, uninstall


@click.group()
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


@click.command()
@click.pass_context
def version(ctx):
    from beiboot.configuration import __VERSION__

    print_formatted_text("Beiboot version: " + __VERSION__)


cli.add_command(version)


@click.group("cluster")
@click.pass_context
def cluster(ctx):
    pass


cluster.add_command(create_cluster)  # type: ignore
cluster.add_command(delete_cluster)  # type: ignore
cluster.add_command(list_clusters)  # type: ignore
cluster.add_command(connect)  # type: ignore
cluster.add_command(disconnect)  # type: ignore
cluster.add_command(inspect)  # type: ignore


cli.add_command(cluster)

cli.add_command(install)
cli.add_command(uninstall)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
