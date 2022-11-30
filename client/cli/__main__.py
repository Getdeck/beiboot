import click
from prompt_toolkit import print_formatted_text

from beiboot.configuration import ClientConfiguration

from cli.cluster import create_cluster, delete, list_clusters, connect, inspect


@click.group()
@click.option(
    "--kubeconfig",
    help="Path to the kubeconfig file to use instead of loading the default",
)
@click.option(
    "--context",
    help="Context of the kubeconfig file to use instead of 'default'",
)
@click.pass_context
def cli(ctx, kubeconfig, context):
    ctx.ensure_object(dict)
    ctx.obj["config"] = ClientConfiguration(
        kube_config_file=kubeconfig, kube_context=context
    )


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


cluster.add_command(create_cluster)
cluster.add_command(delete)
cluster.add_command(list_clusters)
cluster.add_command(connect)
cluster.add_command(inspect)


cli.add_command(cluster)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
