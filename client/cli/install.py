import dataclasses

import click

from beiboot.misc.comps import COMPONENTS
from beiboot.misc.install import synthesize_config_as_yaml
from beiboot.misc.uninstall import (
    remove_all_beiboots,
    remove_beiboot_crds,
    remove_beiboot_namespace,
    remove_remainder_bbts,
    remove_remainder_beiboot_namespaces,
    remove_beiboot_rbac,
    remove_beiboot_webhooks,
)
from beiboot.types import InstallOptions

from cli.console import error, info
from cli.utils import multi_options, standard_error_handler
from cli.__main__ import cli as _cli

PRESETS = {
    "gke": InstallOptions(
        storage_class="standard-rwo", shelf_storage_class="standard-rwo"
    ),
}


@_cli.command(
    "install",
    help="Create and print the Kubernetes configs for Beiboot; use it so 'beibootctl install [options] | kubectl apply -f -",
)
@click.option(
    "--component",
    "--comp",
    help=f"Limit config creation to this component (available: {','.join([c.__name__.split('.')[-1] for c in COMPONENTS])})",
    type=str,
    multiple=True,
)
@click.option(
    "--preset",
    help=f"Set configs from a preset (available: {','.join(PRESETS.keys())})",
    type=str,
)
@click.pass_context
@multi_options(InstallOptions.to_cli_options())
@standard_error_handler
def install(ctx, component, preset, **kwargs):
    if preset:
        presetoptions = PRESETS.get(preset)
        if not presetoptions:
            raise RuntimeError(f"Preset {preset} not available. ")
        presetoptions = dataclasses.asdict(presetoptions)
        presetoptions.update({k: v for k, v in kwargs.items() if v is not None})
        options = InstallOptions(**presetoptions)
    else:
        options = InstallOptions(**{k: v for k, v in kwargs.items() if v is not None})
    click.echo(synthesize_config_as_yaml(options=options, components=component))


@_cli.command(
    "uninstall", help="Removes the Beiboot installation from the host cluster"
)
@click.option("--force", "-f", help="Delete without promt", is_flag=True)
@click.option(
    "--namespace",
    "-ns",
    help="The namespace Beiboot was installed to (default: getdeck)",
    type=str,
)
@click.pass_context
def uninstall(ctx, force, namespace):
    if not force:
        click.confirm(
            "Do you want to remove all Beiboot components from this cluster?",
            abort=True,
        )
    if namespace:
        ctx.obj["config"].NAMESPACE = namespace
    click.echo("Removing all Beiboots")
    try:
        remove_all_beiboots(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))

    click.echo("Removing remainder Beiboot namespaces")
    try:
        namespaces = remove_remainder_beiboot_namespaces(config=ctx.obj["config"])
        if namespaces:
            info(
                f"The following namespaces are not removed: {','.join(namespaces)}. They will be removed in a future version."
            )
    except Exception as e:
        error(str(e))

    click.echo("Removing remainder Beiboot objects")
    try:
        remove_remainder_bbts(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))

    click.echo("Removing Beiboot CRDs")
    try:
        remove_beiboot_crds(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))

    click.echo("Removing RBAC objects")
    try:
        remove_beiboot_rbac(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))

    click.echo("Removing ValidatingWebhook")
    try:
        remove_beiboot_webhooks(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))

    click.echo("Removing Beiboot namespace")
    try:
        remove_beiboot_namespace(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))
