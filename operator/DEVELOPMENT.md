# Getdeck Beiboot Operator Development
This is the Operator running Beiboot's cluster side components. The Operator
contains the following components:
* an object handler for _beiboot_ resources (CRD, see: https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
* a state machine implementation for beiboots (logical K8s cluster) to set up, tear down, monitor, and reconciliation of clusters
* an AdmissionWebhook to validate beiboot objects upon creation

The operator is written using the [kopf framework](https://github.com/nolar/kopf).

## Prerequisites
It's simple to get started working on the Operator. You only need a Kubernetes cluster and the [Poetry](https://python-poetry.org/) environment.

### Kubernetes
Basically, any Kubernetes cluster will do. The following describes a local setup using [Minikube](https://minikube.sigs.k8s.io/docs/).

Assuming you have Minikube installed, please run the following on your terminal:

1) Create a Kubernetes cluster using the Docker driver
```bash
> minikube start -p beiboot --cpus=max --memory=4000 --driver=docker --addons=default-storageclass storage-provisioner
```
2) The `kubectl` context will be set automatically to this cluster
3) Create the `getdeck` namespace: `kubectl create ns getdeck`.

### Poetry
Please follow the [Poetry documentation](https://python-poetry.org/docs/) on how to get started with it.
From the `operator/` directory you can run all configured tools (including the operator) using `poetry run ...`.
Important tools:
* `poetry run black .` - the code base is styled using [black](https://github.com/psf/black)
* `poetry run flake8` - [flake8](https://flake8.pycqa.org/en/latest/) runs a static code analysis
* `poetry run mypy` - [mypy](https://github.com/python/mypy) analyses static typing

Please be aware that these tools are checked in the CI pipeline. If any of them fails, the code can not be merged.


## Starting the Operator
While being connected to the development host Kubernetes cluster, it's as simple as
```bash
> poetry run kopf run -A main.py
```
The Operator starts on your host and connects to the cluster almost the same way it will do later in production. You
can follow the log in the console and see what's going on.

When starting the Operator, the following happens:
1) _kopf_ connects the handler to Kubernetes' APIs (please consult kopf's documentation for more details)
2) The Operator registers the Kubernetes API extension for _beiboot.getdeck.dev_ 
3) It writes the default cluster parameter configuration to the ConfigMap `beiboot-config` in namespace `getdeck`
(Please follow the code in `beiboot/handler/components.py`).

The Operator is ready once the log says so. You can now create a beiboot object based on your requirements.
### Remarks
You can start with a beiboot object from the `beiboot/operator/tests/` directory:
```bash
> kubectl -n getdeck apply -f tests/fixtures/simple-beiboot.yaml
```

## Writing code
In order for code changes to become effective, you have to restart the kopf process. The Operator will resume pending
operations.

### Remarks
* The kopf framework heavily relies on async structures, please use it as much as possible to keep the Operator responsive to concurrent activities in the cluster
* The ValidationWebhooks cannot be registered that simple in a local environment, please use tests
* Most of the execution happens in `beiboot/operator/beiboot/clusterstate.py` (the state machine implementation) and `beiboot/operator/beiboot/handler/beiboots.py` (the reactive handlers for beiboot objects)

## Testing
Please add a test case for every new feature and other code changes alike. Please add both:
* unit tests in `beiboot/operator/tests/unit/` in a new or existing module
* an integration/e2e test in `beiboot/operator/tests/e2e/` with a new module

### Writing a test
We're using [pytest](https://docs.pytest.org/) to run the test suite. Please write functions as documented.
If you need a K8s cluster API for your test case, it's as simple as loading a fixture:
* `kubeconfig` (for a Minikube-based ephemeral test cluster)
* `kubectl` (for a `kubectl` command wrapper in a matching K8s version)

#### Example: testing a function containing a K8s API call
```python
def test_myfunction(kubeconfig):
    from beiboot import myfunction  # important: always import locally
    
    result = myfunction()  # call a function that depends on K8s  
```
Adding the `kubeconfig` parameter to any function will cause `pytest` to set up a fresh Kubernetes cluster and
execute the test function.  
**Important:** You have to import such functions under test locally, i.e. within the test function. If you import the
function under test globally (module level) it can cause to instantiate the K8s API object before actually creating the
cluster which will make the K8s API object not being able to talk to the test cluster. This behavior is caused by the wrong
order of calling `kubenertes.config.load_kube_config()` and creating the cluster.

#### Example: testing a function with kubectl
```python
def test_myfunction(kubeconfig, kubectl):
    from beiboot import myfunction  # important: always import locally
    
    kubectl(["create", "namespace", "blubb"])  # prime the cluster with any kubectl operation
    myfunction()
    output = kubectl(["-n", "blubb", "get", "pods"])  # get kubectl output for assert operations
    assert "mypod" in output
```
Adding the `kubectl` parameter to any function will cause `pytest` to provide a `kubectl` function. The signature
is `kubectl(command: list[str]) -> str`. Please always tokenize the command as a list of strings.
Using `kubectl` without `kubeconfig` seems to make no sense.

### Running the tests
Please run the test with Poetry and coverage like so (`pwd` is `beiboot/operator/`):
* `poetry run coverage run -m pytest -x -s tests/` (for all tests; ~12min)
* `poetry run coverage run -m pytest -x -s tests/e2e/` (for all end to end tests; ~10min)
* `poetry run coverage run -m pytest -x -s tests/unit/` (for all unit tests; ~2min)
* `poetry run coverage run -m pytest -x -s tests/unit/tests_utils.py` (for one test module)