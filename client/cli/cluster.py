import time

import click
from prompt_toolkit import print_formatted_text
from prompt_toolkit.shortcuts import ProgressBar
from prompt_toolkit.shortcuts.progress_bar import formatters
from tabulate import tabulate


from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters, BeibootState
from cli.console import info, create_pbar
from cli.utils import standard_error_handler


@click.command("create")
@click.argument("name")
@click.option(
    "-p",
    "--ports",
    multiple=True,
    help="Ports to map (in the form '<local-port>:<cluster-port>', e.g. 8080:80)",
)
@click.option("-N", "--nodes", help="The number of cluster nodes to spawn")
@click.option(
    "--max-lifetime",
    help="The definitive lifetime for this cluster (e.g. 2h or 2h30m); units are d(ays), h(ours), m(inutes).",
)
@click.option(
    "--max-session-timeout",
    help="The timeout for for this cluster if no client is connected (e.g. 2h or 2h30m); units are d(ays), h(ours), m(inutes).",
)
@click.option(
    "--cluster-ready-timeout",
    help="The timeout for a cluster to enter READY state (in seconds)",
)
@click.option("--server-requests-cpu", type=float)
@click.option("--server-requests-memory", type=str)
@click.option("--node-requests-cpu", type=float)
@click.option("--node-requests-memory", type=str)
@click.option("--server-storage", type=str)
@click.option("--node-storage", type=str)
@click.pass_context
@standard_error_handler
def create_cluster(
    ctx,
    name,
    ports,
    nodes,
    max_lifetime,
    max_session_timeout,
    cluster_ready_timeout,
    server_requests_cpu,
    node_requests_cpu,
    server_requests_memory,
    node_requests_memory,
    server_storage,
    node_storage,
):
    server_requests = {}
    node_requests = {}
    if server_requests_cpu:
        server_requests.update({"cpu": server_requests_cpu})
    if server_requests_memory:
        server_requests.update({"memory": server_requests_memory})
    if node_requests_cpu:
        node_requests.update({"cpu": node_requests_cpu})
    if node_requests_memory:
        node_requests.update({"memory": node_requests_memory})

    parameters = BeibootParameters(
        ports=ports,
        nodes=nodes,
        lifetime=max_lifetime,
        session_timeout=max_session_timeout,
        cluster_timeout=cluster_ready_timeout,
        server_resources=server_requests if server_requests else None,
        node_resources=node_requests if node_requests else None,
        node_storage=node_storage,
        server_storage=server_storage,
    )
    req = BeibootRequest(name=name, parameters=parameters)
    beiboot = api.create(req, config=ctx.obj["config"])

    state_pipeline = [
        BeibootState.REQUESTED,
        BeibootState.CREATING,
        BeibootState.PENDING,
        BeibootState.RUNNING,
        BeibootState.READY,
    ]

    custom_formatters = [
        formatters.Text("[", style="class:percentage"),
        formatters.Percentage(),
        formatters.Text("]", style="class:percentage"),
        formatters.Text(" "),
        formatters.Bar(sym_a="=", sym_b=">", sym_c="."),
        formatters.Text("  "),
    ]

    with ProgressBar(formatters=custom_formatters) as pb:
        for state in pb(state_pipeline):
            pb.title = f"Beiboot: {state.value}"
            if state_pipeline.index(beiboot.state) > state_pipeline.index(state):
                continue
            elif beiboot.state == BeibootState.ERROR:
                raise RuntimeError("This Beiboot cluster entered ERROR state")
            elif beiboot.state == BeibootState.READY:
                continue
            while beiboot.state == state:
                beiboot._fetch_object()
                if beiboot.state == BeibootState.ERROR:
                    raise RuntimeError("This Beiboot cluster entered ERROR state")
                time.sleep(0.5)


@click.command("delete")
@click.argument("name")
@click.pass_context
@standard_error_handler
def delete(ctx, name):
    api.delete_by_name(name)


@click.command("list")
@click.pass_context
@standard_error_handler
def list_clusters(ctx):
    beiboots = api.read_all(config=ctx.obj["config"])
    if beiboots:
        tab = [(bbt.name, bbt.namespace, bbt.state.value) for bbt in beiboots]
        print_formatted_text(tabulate(tab, headers=["Name", "Namespace", "State"]))
    else:
        info("No Beiboot running")


@click.command()
@click.argument("name")
@click.pass_context
def watch(ctx, name):
    pass


@click.command()
@click.argument("name")
@click.pass_context
def connect(ctx, name):
    pass
