import click
from prompt_toolkit import print_formatted_text
from tabulate import tabulate

from beiboot import api
from cli.__main__ import shelve
from cli.console import info
from cli.utils import standard_error_handler


@shelve.command("create", help="Shelve a Beiboot cluster")
@click.argument("cluster_name")
@click.option(
    "--shelf-name",
    help="Name of the shelf-object, needs to be unique",
)
@click.option(
    "--volume-snapshot-class",
    help="Name of the volume-snapshot-class, otherwise it will be automatically chosen",
)
def shelve_cluster(
        ctx,
        cluster_name,
        shelf_name,
        volume_snapshot_class,
):
    # TODO
    pass


@shelve.command("list", alias=["ls"], help="List shelved Beiboot clusters (filtered when labels option is used)")
@click.option(
    "--label",
    "-l",
    type=str,
    multiple=True,
    help="Filter Beiboots based on the label (use multiple times, e.g. --label label=value)",
)
@click.pass_context
@standard_error_handler
def list_shelves(ctx, label):
    if label:
        _labels = dict([_l.split("=") for _l in label])
    else:
        _labels = {}
    shelves = api.read_all_shelves(_labels, config=ctx.obj["config"])
    if shelves:
        tab = [
            (
                shelf.uid,
                shelf.name,
                shelf.namespace,
                shelf.state.value
            )
            for shelf in shelves
        ]
        print_formatted_text(
            tabulate(
                tab,
                headers=[
                    "UID",
                    "Name",
                    "Namespace",
                    "State",
                ],
            )
        )
    else:
        info("No Shelves available")
