import inspect
import logging
import string
import random
from typing import List, Optional

import kubernetes as k8s
from statemachine.exceptions import MultipleTransitionCallbacksFound
from statemachine.statemachine import (
    StateMachineMetaclass,
    BaseStateMachine,
    Transition,
    State,
)


from beiboot.configuration import ClusterConfiguration, BeibootConfiguration


logger = logging.getLogger("beiboot")


def generate_token(length=10) -> str:
    """
    It generates a random string of length (default 10), consisting of uppercase letters and digits

    :param length: The length of the token to be generated, defaults to 10 (optional)
    :return: A string of random characters and numbers.
    """
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


def get_external_node_ips(api_instance: k8s.client.CoreV1Api) -> List[Optional[str]]:
    """
    It gets the external IP addresses of all the nodes in the Kubernetes cluster

    :param api_instance: k8s.client.CoreV1Api
    :type api_instance: k8s.client.CoreV1Api
    :return: A list of IP addresses of the Kubernetes nodes.
    """
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


def get_namespace_name(name: str, cluster_config: ClusterConfiguration) -> str:
    """
    It takes a name and a cluster configuration and returns a namespace name

    :param name: The name of the namespace
    :type name: str
    :param cluster_config: This is the cluster configuration object that we created earlier
    :type cluster_config: ClusterConfiguration
    :return: The namespace name.
    """
    namespace = f"{cluster_config.namespacePrefix}-{name}"
    return namespace


def get_beiboot_for_namespace(
    namespace: str,
    api_instance: k8s.client.CustomObjectsApi,
    configuration: BeibootConfiguration,
):
    """
    It returns the Beiboot object for a given namespace

    :param namespace: the namespace to look for a beiboot in
    :type namespace: str
    :param api_instance: the kubernetes client
    :type api_instance: k8s.client.CustomObjectsApi
    :param configuration: BeibootConfiguration
    :type configuration: BeibootConfiguration
    :return: A dict with the following keys:
        api_version
        kind
        metadata
        spec
        status
    """

    class AttrDict(dict):
        def __init__(self, *args, **kwargs):
            super(AttrDict, self).__init__(*args, **kwargs)
            self.__dict__ = self

    beiboots = api_instance.list_namespaced_custom_object(
        group="getdeck.dev",
        version="v1",
        namespace=configuration.NAMESPACE,
        plural="beiboots",
    )
    for bbt in beiboots["items"]:
        if bbt["beibootNamespace"] == namespace:
            # need to wrap this for correct later use
            return AttrDict(bbt)
    else:
        return None


def get_label_selector(labels: dict[str, str]) -> str:
    return ",".join(["{0}={1}".format(*label) for label in list(labels.items())])


# It's a subclass of the `Transition` class that adds a `run` method that runs the transition asynchronously
class AsyncTransition(Transition):
    async def _run(self, machine, *args, **kwargs):
        self._verify_can_run(machine)
        self._validate(*args, **kwargs)
        return await machine._activate(self, *args, **kwargs)


# It's a state that can be used in an asynchronous context
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


# It's a state machine that can be used in an asynchronous context
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
