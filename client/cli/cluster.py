import time

import click
from prompt_toolkit import print_formatted_text
from prompt_toolkit.shortcuts import ProgressBar
from tabulate import tabulate


from beiboot import api
from beiboot.types import BeibootRequest, BeibootParameters, BeibootState
from cli.console import (
    info,
    last_event_by_timestamp_toolbar,
    cluster_create_formatters,
    success,
    heading,
)
from cli.utils import standard_error_handler


@click.command("create")
@click.argument("name")
@click.option(
    "--k8s-version",
    multiple=True,
    help="The requested Kubernetes API version (e.g. 1.25.1)",
)
@click.option(
    "-p",
    "--ports",
    multiple=True,
    help="Ports to map (in the form '<local-port>:<cluster-port>', e.g. 8080:80)",
)
@click.option("-N", "--nodes", help="The number of cluster nodes to spawn", type=int)
@click.option(
    "--max-lifetime",
    help="The definitive lifetime for this cluster (e.g. 2h or 2h30m); units are d(ays), h(ours), m(inutes).",
    type=str,
)
@click.option(
    "--max-session-timeout",
    help="The timeout for for this cluster if no client is connected (e.g. 2h or 2h30m); units are d(ays), h(ours), m(inutes).",
    type=str,
)
@click.option(
    "--cluster-ready-timeout",
    help="The timeout for a cluster to enter READY state (in seconds)",
    type=int,
)
@click.option("--server-requests-cpu", type=float)
@click.option("--server-requests-memory", type=str)
@click.option("--node-requests-cpu", type=float)
@click.option("--node-requests-memory", type=str)
@click.option("--server-storage", type=str)
@click.option("--node-storage", type=str)
@click.option(
    "-s",
    "--nowait",
    is_flag=True,
)
@click.pass_context
@standard_error_handler
def create_cluster(
    ctx,
    name,
    k8s_version,
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
    nowait,
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
        k8sVersion=k8s_version,
        ports=ports,
        nodes=nodes,
        maxLifetime=max_lifetime,
        maxSessionTimeout=max_session_timeout,
        clusterReadyTimeout=cluster_ready_timeout,
        serverResources={"requests": server_requests} if server_requests else None,
        nodeResources={"requests": node_requests} if node_requests else None,
        nodeStorageRequests=node_storage,
        serverStorageRequests=server_storage,
    )
    req = BeibootRequest(name=name, parameters=parameters)
    start_time = time.time()
    beiboot = api.create(req, config=ctx.obj["config"])

    if not nowait:
        state_pipeline = [
            BeibootState.REQUESTED,
            BeibootState.CREATING,
            BeibootState.PENDING,
            BeibootState.RUNNING,
            BeibootState.READY,
        ]

        with ProgressBar(
            formatters=cluster_create_formatters,
            title=f"Beiboot: {beiboot.state}",
            bottom_toolbar=last_event_by_timestamp_toolbar(beiboot.events_by_timestamp),
        ) as pb:
            for state in pb(state_pipeline):
                current_state = beiboot.state
                pb.title = f"Beiboot: {current_state}"
                pb.bottom_toolbar = last_event_by_timestamp_toolbar(
                    beiboot.events_by_timestamp
                )
                if current_state == BeibootState.ERROR:
                    raise RuntimeError("This Beiboot cluster entered ERROR state")
                if state_pipeline.index(current_state) > state_pipeline.index(state):
                    continue
                elif current_state == BeibootState.READY:
                    continue
                while beiboot.state == state:
                    pb.bottom_toolbar = last_event_by_timestamp_toolbar(
                        beiboot.events_by_timestamp
                    )
                    if beiboot.state == BeibootState.ERROR:
                        raise RuntimeError("This Beiboot cluster entered ERROR state")
                    time.sleep(0.5)
        success(f"Beiboot cluster ready in {time.time() - start_time:.1f} seconds")


@click.command("delete")
@click.argument("name")
@click.pass_context
@standard_error_handler
def delete(ctx, name):
    api.delete_by_name(name)
    info(f"Beiboot '{name}' marked for deletion")


@click.command("list")
@click.pass_context
@standard_error_handler
def list_clusters(ctx):
    beiboots = api.read_all(config=ctx.obj["config"])
    if beiboots:
        tab = [
            (bbt.uid, bbt.name, bbt.namespace, bbt.state.value, bbt.sunset or "-")
            for bbt in beiboots
        ]
        print_formatted_text(
            tabulate(tab, headers=["UID", "Name", "Namespace", "State", "Sunset"])
        )
    else:
        info("No Beiboot(s) running")


@click.command("inspect")
@click.argument("name")
@click.pass_context
@standard_error_handler
def inspect(ctx, name):
    import dataclasses

    beiboot = api.read(name=name)
    info("Name: " + beiboot.name)
    info("UID: " + beiboot.uid)
    info("Namespace: " + beiboot.namespace)
    info("State: " + beiboot.state.value)

    heading("\nParameters:")
    paramtab = [
        (str(key), str(value))
        for key, value in dataclasses.asdict(beiboot.parameters).items()
    ]
    print_formatted_text(tabulate(paramtab, headers=["Key", "Value"]))
    heading("\nEvents:")
    eventtab = [
        (str(date), event.get("reason") or "-", event.get("message")[:100] or "-")
        for date, event in beiboot.events_by_timestamp.items()
    ]
    print_formatted_text(tabulate(eventtab, headers=["Date", "Reason", "Message"]))


@click.command("connect")
@click.argument("name")
@click.pass_context
def connect(ctx, name):
    pass
