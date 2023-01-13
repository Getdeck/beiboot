from datetime import datetime

import click
from prompt_toolkit import print_formatted_text
from tabulate import tabulate

from beiboot import api
from beiboot.types import ShelfRequest
from cli.__main__ import shelf
from cli.console import info
from cli.utils import standard_error_handler


@shelf.command("create", help="Shelve a Beiboot cluster")
@click.argument("cluster_name")
@click.option(
    "--shelf-name",
    help="Name of the shelf-object, needs to be unique",
)
@click.option(
    "--volume-snapshot-class",
    help="Name of the volume-snapshot-class, otherwise it will be automatically chosen",
)
@click.option(
    "--label",
    "-l",
    type=str,
    multiple=True,
    help="Add labels to this Shelf (use multiple times, e.g. --label label=value)",
)
@click.pass_context
@standard_error_handler
def shelve_cluster(
        ctx,
        cluster_name,
        shelf_name,
        volume_snapshot_class,
        label,
):
    # TODO finish
    if shelf_name:
        _shelf_name = shelf_name
    else:
        _shelf_name = f"{datetime.now().strftime('%y%m%d%H%M%S')}_{cluster_name}"

    # TODO: get namespace from cluster_name

    if label:
        _labels = dict([_l.split("=") for _l in label])
    else:
        _labels = {}

    volume_snapshot_contents = []

    req = ShelfRequest(
        name=_shelf_name,
        namespace="foo",
        labels=_labels,
        volume_snapshot_contents=volume_snapshot_contents
    )
    shelf = api.create_shelf(req, config=ctx.obj["config"])


@shelf.command(
    "delete",
    alias=["rm", "remove"],
    help="Mark a Shelf for deletion"
)
@click.argument("name")
@click.pass_context
@standard_error_handler
def delete_shelf(ctx, name):
    api.delete_shelf_by_name(name)
    info(f"Shelf '{name}' marked for deletion")


@shelf.command("list", alias=["ls"], help="List shelved Beiboot clusters (filtered when labels option is used)")
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
                    "State",
                ],
            )
        )
    else:
        info("No Shelves available")
