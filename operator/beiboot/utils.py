import inspect
import logging
import string
import random
from asyncio import sleep
from typing import List, Optional, TYPE_CHECKING

import kubernetes as k8s
from statemachine.exceptions import MultipleTransitionCallbacksFound
from statemachine.statemachine import (
    StateMachineMetaclass,
    BaseStateMachine,
    Transition,
    State,
)


from beiboot.configuration import ClusterConfiguration, BeibootConfiguration

if TYPE_CHECKING:
    from beiboot.clusterstate import BeibootCluster

logger = logging.getLogger("beiboot")


def generate_token(length=10) -> str:
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(length)
    )


def exec_command_pod(
    api_instance: k8s.client.CoreV1Api,
    pod_name: str,
    namespace: str,
    container_name: str,
    command: List[str],
    run_async: bool = False,
) -> str:
    """
    Exec a command on a Pod and exit
    :param api_instance: a CoreV1Api instance
    :param pod_name: the name of the Pod to exec this command on
    :param namespace: the namespace this Pod is running in
    :param container_name: the container name of this Pod
    :param command: command as List[str]
    :param run_async: run this command async
    :return: the result output as str
    """
    if run_async:
        resp = api_instance.connect_get_namespaced_pod_exec(
            pod_name,
            namespace,
            container=container_name,
            command=command,
            stderr=False,
            stdin=False,
            stdout=False,
            tty=False,
            async_req=True,
        )
    else:
        resp = k8s.stream.stream(
            api_instance.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            container=container_name,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
    if not run_async:
        logger.debug("Response: " + resp)
    return resp


async def check_workload_running(cluster: "BeibootCluster", silent=False) -> bool:
    i = 0
    # a primitive timeout of configuration.API_SERVER_STARTUP_TIMEOUT in seconds
    if not silent:
        logger.info("Waiting for workload to become running...")
    while i <= cluster.parameters.clusterReadyTimeout:
        if await cluster.provider.running():
            if not silent:
                logger.info("Cluster is now running")
            return True
        else:
            await sleep(1)
            i += 1
            continue
    # reached this in an error case a) timout (build took too long) or b) build could not be successfully executed
    logger.error("Cluster did not become running")
    return False


async def check_workload_ready(cluster: "BeibootCluster", silent=False) -> bool:
    i = 0
    # a primitive timeout of configuration.API_SERVER_STARTUP_TIMEOUT in seconds
    if not silent:
        logger.info("Waiting for workload to become ready...")
    while i <= cluster.parameters.clusterReadyTimeout:
        if await cluster.provider.ready():
            if not silent:
                logger.info("Cluster is now ready")
            return True
        else:
            await sleep(1)
            i += 1
            continue
    # reached this in an error case a) timout (build took too long) or b) build could not be successfully executed
    logger.error("Cluster did not become ready")
    return False


def get_external_node_ips(api_instance: k8s.client.CoreV1Api) -> List[Optional[str]]:
    ips = []
    try:
        nodes = api_instance.list_node()
    except Exception as e:  # noqa
        logger.error("Could not read Kubernetes nodes: " + str(e))
        return []

    for node in nodes.items:
        try:
            for address in node.status.addresses:
                if address.type == "ExternalIP":
                    ips.append(str(address.address))
        except Exception as e:  # noqa
            logger.error("Could not read Kubernetes node: " + str(e))
    logger.debug(ips)
    return ips


def get_taken_gefyra_ports(
    api_instance: k8s.client.CustomObjectsApi, config: BeibootConfiguration
) -> List[Optional[int]]:
    try:
        beiboots = api_instance.list_namespaced_custom_object(
            namespace=config.NAMESPACE,
            group="getdeck.dev",
            plural="beiboots",
            version="v1",
        )
    except Exception as e:  # noqa
        logger.error(
            "Could not read Beiboot objects from the cluster due to the following error: "
            + str(e)
        )
        return []
    taken_ports = []
    for beiboot in beiboots["items"]:
        if gefyra := beiboot.get("gefyra"):
            port = gefyra.get("port")
            try:
                taken_ports.append(int(port))
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Cannot read Gefyra ports from {beiboot.metadata.name} due to: {e}"
                )
        else:
            continue
    return taken_ports


def get_namespace_name(name: str, cluster_config: ClusterConfiguration) -> str:
    namespace = f"{cluster_config.namespacePrefix}-{name}"
    return namespace


class AsyncTransition(Transition):
    async def _run(self, machine, *args, **kwargs):
        self._verify_can_run(machine)
        self._validate(*args, **kwargs)
        return await machine._activate(self, *args, **kwargs)


class AsyncState(State):
    def _to_(self, *states):
        transition = AsyncTransition(self, *states)
        self.transitions.append(transition)
        return transition

    def _from_(self, *states):
        combined = None
        for origin in states:
            transition = AsyncTransition(origin, self)
            origin.transitions.append(transition)
            if combined is None:
                combined = transition
            else:
                combined |= transition
        return combined


class AsyncStateMachine(BaseStateMachine):
    async def _activate(self, transition, *args, **kwargs):
        bounded_on_event = getattr(self, "on_{}".format(transition.identifier), None)
        on_event = transition.on_execute

        if bounded_on_event and on_event and bounded_on_event != on_event:
            raise MultipleTransitionCallbacksFound(transition)

        result = None
        if inspect.iscoroutinefunction(bounded_on_event):
            result = await bounded_on_event(*args, **kwargs)
        elif callable(bounded_on_event):
            result = bounded_on_event(*args, **kwargs)
        elif callable(on_event):
            result = on_event(self, *args, **kwargs)

        result, destination = transition._get_destination(result)

        bounded_on_exit_state_event = getattr(self, "on_exit_state", None)
        if callable(bounded_on_exit_state_event):
            bounded_on_exit_state_event(self.current_state)

        bounded_on_exit_specific_state_event = getattr(
            self, "on_exit_{}".format(self.current_state.identifier), None
        )
        if callable(bounded_on_exit_specific_state_event):
            bounded_on_exit_specific_state_event()

        self.current_state = destination

        bounded_on_enter_state_event = getattr(self, "on_enter_state", None)
        if callable(bounded_on_enter_state_event):
            bounded_on_enter_state_event(destination)

        bounded_on_enter_specific_state_event = getattr(
            self, "on_enter_{}".format(destination.identifier), None
        )
        if inspect.iscoroutinefunction(bounded_on_enter_specific_state_event):
            await bounded_on_enter_specific_state_event(*args, **kwargs)
        elif callable(bounded_on_enter_specific_state_event):
            bounded_on_enter_specific_state_event()

        return result


StateMachine = StateMachineMetaclass("StateMachine", (AsyncStateMachine,), {})
