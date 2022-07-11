<div id="top"></div>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![Coverage Information][coveralls-shield]][coveralls-url]


<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/Getdeck/beiboot">
    <img src="https://github.com/Getdeck/beiboot/raw/main/docs/static/img/logo.png" alt="Getdeck Beiboot Logo"/>
  </a>

  <h3 align="center">Getdeck Beiboot</h3>

  <p align="center">
    Getdeck Beiboot is a Kubernetes-in-Kubernetes solution. It allows creating multiple logical Kubernetes environments within one physical host cluster.
    <br />
    <a href="https://getdeck.dev/docs/"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Getdeck/beiboot/issues">Report Bug</a>
    ·
    <a href="https://github.com/Getdeck/beiboot/issues">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#features">Features</a></li>
        <li><a href="#what-is-hybrid-cloud-development">What is hybrid cloud development?</a></li>
        <li><a href="#kubernetes-in-kubernetes">Kubernetes-in-Kubernetes</a></li>
      </ul>
    </li>
    <li>
      <a href="#built-with">Built with</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#install-the-operator-to-the-kubernetes-host-cluster">Install the operator to the Kubernetes host cluster</a></li>
        <li><a href="#usage">Usage</a></li>
      </ul>
    </li>
    <li><a href="#license">License</a></li>
    <li><a href="#reporting-bugs">Reporting bugs</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About the project
_Getdeck Beiboot_ (or just Beiboot for brevity) is a Kubernetes-in-Kubernetes solution. It was born from the idea to 
provide Getdeck users a simple yet flexible solution to spin up **hybrid cloud development** infrastructure. This is 
useful for development workloads which grew too large to run on a development machine (or with pony workloads on MacOS 
and Windows machines).

### Features
Beiboot offers:
- to create a fresh ad-hoc Kubernetes cluster in seconds (much faster than Terraform or your favorite cloud-provider)
- run isolated workloads within Kubernetes; cheap with the best resource utilization
- automatic distribution of _kubeconfig_ and proxied connection on clients
- built-in support for [Gefyra](https://gefyra.dev)

### What is **hybrid cloud development**?  
For an efficient Kubernetes-based development workflow it is important to run as many dependant (or attached) services of
the application under development in Kubernetes - even during development time. Almost all the attached services run in a
Kubernetes cluster somewhere in the cloud. However, the application currently under development runs on the developer's machine
and behaves as it would run directly in that Kubernetes cluster.  
The developed application: runs locally - all the rest of the development workload: runs in the cloud = hybrid cloud development.  
Check out [Gefyra](https://gefyra.dev) to see how this works.

### Kubernetes-in-Kubernetes
There are a couple of aspects why a logical ("virtual") Kubernetes cluster running within a physical Kubernetes cluster 
is beneficial. The main focus currently is spinning up on demand Kubernetes clusters for development and testing 
purposes, although Beiboot has potential for other scenarios, too (e.g. strong workload isolation, multi-tenancy 
and security).    
  
Beiboot comes with a Kubernetes operator which handles the ad-hoc logical clusters based on the requested parameters. 
This includes the Kubernetes version, the way of exposing the cluster, lifetime and so on.  

<div align="center">
    <img src="https://github.com/Getdeck/beiboot/raw/main/docs/static/img/beiboot-ops.png" alt="Beiboot operator"/>
</div>

<p align="right">(<a href="#top">back to top</a>)</p> 

## Built with
Beiboot builds on top of the following popular open-source technologies:

### k3s
[*k3s*](https://rancher.com/docs/k3s/latest/en/) is the foundation for the logical Kubernetes clusters. 

### Docker
[*Docker*](https://docker.io) is currently used in order to run the proxy setup for clients.


<p align="right">(<a href="#top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

### Install the operator to the Kubernetes host cluster
Install the Getdeck Beiboot operator with:
```bash
kubectl apply -f https://raw.githubusercontent.com/Getdeck/beiboot/main/operator/manifests/beiboot.yaml
```
This creates the target namespace `getdeck` for the operator and kubernetes extension (CRD) `beiboot, beiboots, bbt`.

<p align="right">(<a href="#top">back to top</a>)</p>

### Usage
There are multiple ways you can manage Beiboot in a Kubernetes host cluster.

#### Beiboot Python client
Getdeck Beiboot comes with a Python client. You find it in this repository under `client/` or on PyPI. The API offers
a couple of functions to manage Beiboot and establish a local connection to logical Kubernetes clusters.

##### Using Poetry
**Important:** Using Poetry is only intended for development and testing purposes of Beiboot itself.
In order to create a Beiboot and automatically connect to it, run from the `client/` directory:
```bash
poetry run create cluster-1
```
and it will output:
```
[INFO] Now creating Beiboot cluster-1
[INFO] Waiting for the cluster to become ready
[INFO] KUBECONFIG file for cluster-1 written to: /home/<user>/.getdeck/cluster-1.yaml.
[INFO] You can now run 'export KUBECONFIG=/home/mschilonka/.getdeck/cluster-1.yaml' and work with the cluster.
```

A local Docker container has been started to proxy the Kubernes API to you local host.
```
> docker ps
CONTAINER ID   IMAGE                            COMMAND                  CREATED         STATUS         PORTS  NAMES
e17...1b9db2   quay.io/getdeck/tooler:latest    "kubectl port-forwar…"   2 minutes ago   Up 2 minutes          getdeck-proxy-cluster-1
```

The following system architecture has been set up with this example.
<div align="center">
    <img src="https://github.com/Getdeck/beiboot/raw/main/docs/static/img/beiboot-client.png" alt="Beiboot client"/>
</div>

Delete the logical Kubernetes cluster again with:
```bash
poetry run remove cluster-1
```

##### API documentation
Coming soon.

#### Getdeck CLI
Beiboot will soon be integrated with [Getdeck](https://getdeck.dev/docs/deckfile/specs#provider) as a new "provider", so
you can use _Deckfiles_ as origin for Beiboots.

#### With bare kubectl 
Creating a logical Kubernetes cluster using Beiboot is very easy:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: getdeck.dev/v1
kind: beiboot
metadata:
  name: cluster-1
  namespace: getdeck
provider: k3s
EOF
```
It creates an object of type `beiboot`. Required fields are `name` and `provider` (currently only _k3s_ is supported). 
```bash
> kubectl -n getdeck get bbt 
NAME        AGE
cluster-1   1m22s
```
The cluster is going to be created in namespace `getdeck-bbt-cluster-1` of the host cluster. Once the cluster is ready
you can retrive the _kubeconfig_ from the `beiboot` object running
```bash
kubectl -n getdeck get bbt cluster-1 --no-headers -o=custom-columns=:.kubeconfig.source | base64 -d > cluster-1.yaml
```
**Important:** Please note that this _kubeconfig_ specifies the server to be reachable at `https://127.0.0.1:6443`.
To reach this logical Kubernetes cluster you have to set up a `kubectl port-forward` on your local machine.
```bash
kubectl port-forward -n getdeck-bbt-cluster-1 svc/kubeapi 6443:6443
```
Now, in a different terminal you can set `export KUBECONFIG=<path>/cluster-1.yaml` and you are ready to go. In this
terminal session you can now use `kubectl` just as usual.  

If you wish to remove the logical Kubernetes cluster, please type
```bash
kubectl -n getdeck delete bbt cluster-1
```
and the entire namespace in the host cluster will be gone in a matter of seconds.


<p align="right">(<a href="#top">back to top</a>)</p>

<!-- LICENSE -->
## License
Distributed under the Apache License 2.0. See `LICENSE` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>

## Reporting bugs
If you encounter issues, please create a new issue on GitHub or talk to us on the
[Unikube Slack channel](https://unikubeworkspace.slack.com/). 

<p align="right">(<a href="#top">back to top</a>)</p>

## Acknowledgments
Getdeck Beiboot is sponsored by the [Blueshoe GmbH](https://blueshoe.io). Beiboot heavily relies on the work of [Rancher
k3s](https://rancher.com/docs/k3s/latest/en/).

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/Getdeck/beiboot.svg?style=for-the-badge
[contributors-url]: https://github.com/Getdeck/beiboot/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/Getdeck/beiboot.svg?style=for-the-badge
[forks-url]: https://github.com/Getdeck/beiboot/network/members
[stars-shield]: https://img.shields.io/github/stars/Getdeck/beiboot.svg?style=for-the-badge
[stars-url]: https://github.com/Getdeck/beiboot/stargazers
[issues-shield]: https://img.shields.io/github/issues/Getdeck/beiboot.svg?style=for-the-badge
[issues-url]: https://github.com/Getdeck/beiboot/issues
[license-shield]: https://img.shields.io/github/license/Getdeck/beiboot.svg?style=for-the-badge
[license-url]: https://github.com/Getdeck/beiboot/blob/master/LICENSE.txt
[coveralls-shield]: https://img.shields.io/coveralls/github/Getdeck/beiboot/main?style=for-the-badge
[coveralls-url]: https://coveralls.io/github/Getdeck/beiboot


