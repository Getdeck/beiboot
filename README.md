<div id="top"></div>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![Coverage Information][codecov-shield]][codecov-url]


<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/Getdeck/beiboot">
    <img src="https://github.com/Getdeck/beiboot/raw/main/docs/static/img/logo.png" alt="Getdeck Beiboot Logo"/>
  </a>

  <h3 align="center">Getdeck Beiboot</h3>

  <p align="center">
    Getdeck Beiboot is a Kubernetes-in-Kubernetes solution. It allows managing, snapshotting, and restoring many logical Kubernetes environments running on top of one physical host cluster.
    <br />
    <a href="https://getdeck.dev/beiboot/"><strong>Explore the docs »</strong></a>
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
**The Problem**  
With complex application landscapes, running Kubernetes-based workloads locally becomes infeasible. Swiftly testing applications with different Kubernetes versions can be impossible depending on organizational policies. Spinning up a Kubernetes cluster with Terraform or Cloud providers takes to long for a convenient development workflow or CI pipelines.

**The Solution**  
With Beiboot you only need one host Kubernetes cluster that runs the Getdeck Beiboot operator. Beiboot creates Kubernetes clusters as deployments in a matter of seconds. The operator creates several ways to connect to that cluster and makes it simple to get started working with Kubernetes.

### Features
Beiboot offers:
- to create a fresh ad-hoc Kubernetes cluster in seconds (much faster than Terraform or Cloud-provider)
- automatic management of Beiboot clusters (via lifetime, inactivity, etc.)
- shelve ("snapshot") a running Beiboot cluster with state and restore them as often as needed
- run isolated workloads within Kubernetes; cheap and with the best resource utilization
- automatic distribution of kubeconfig and tunnel connection to clients (using the Beiboot client package)
- built-in support for [Gefyra](https://gefyra.dev)


### Kubernetes-in-Kubernetes
There are many use-cases running a logical ("virtual") Kubernetes cluster within a physical Kubernetes cluster. The main focus of Beiboot is the on-demand creation of Kubernetes clusters for development and testing purposes. Beiboot has potential for other scenarios, too. For example, strong workload isolation, multi-tenancy, CI, security and more.   
  
Beiboot comes with a Kubernetes operator that handles the ad-hoc logical clusters based on the requested parameters. 
This includes the Kubernetes version, the way of exposing the cluster, lifetime and so on. It can also snapshop ("shelve") and restore a cluster many times.

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

### Kopf Framework
[*Kopf*](https://github.com/nolar/kopf) a framework to write Python-based Kubernetes operators.


<p align="right">(<a href="#top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started
### `beibootctl`
Please download the latest version of `beibootctl` from [the GitHub release section](https://github.com/Getdeck/beiboot/releases/latest/) and add it to your path.

### Install the operator to the Kubernetes host cluster
Install the Getdeck Beiboot operator with:
```bash
beibootctl install | kubectl apply -f -
```
This creates the target namespace `getdeck` for the operator and kubernetes extension (CRD) `beiboot, beiboots, bbt`.

[For more information about the installation, check out the docs.](https://getdeck.dev/beiboot/installation/basics/)


### Usage
There are multiple ways you can manage Beiboot in a Kubernetes host cluster. The clients of Beiboot create a mTLS secured connection, making the Beiboot cluster become available on *localhost*. That way,
Beiboot feels like it would run on the developer's machiene.

<div align="center">
    <img src="https://github.com/Getdeck/beiboot/raw/main/docs/static/img/beiboot-client-connection.png" alt="Beiboot client connect"/>
</div>


#### Using `beibootctl`
The static binary `beibootctl` is created for Beiboot administrators. It allows to create, delete, inspect Beiboot clusters and connect to them. [Please check out the documentation.](https://getdeck.dev/beiboot/beibootctl/)

<div align="center">
    <img src="https://github.com/Getdeck/beiboot/raw/main/docs/static/img/beiboot-demo.gif" alt="beibootctl demo"/>
</div>

#### Beiboot Python client
Getdeck Beiboot comes with a Python client. You find it in this repository under `client/` or [on PyPI](https://pypi.org/project/beiboot/). The API offers many functions to manage Beiboot and establish a local connection to Beiboot clusters.

##### Using Poetry
**Important:** Using Poetry is only intended for development and testing purposes of Beiboot itself.
You can use it like so:
```bash
portry run beibootctl ...
```


##### API documentation
Coming soon.

#### Getdeck CLI
Beiboot will soon be integrated with [Getdeck](https://getdeck.dev/docs/deckfile/specs#provider) as a new "provider", so
you can use _Deckfiles_ as origin for Beiboots.

#### Beiboot Desktop
We're currently working on releasing [a desktop client](https://github.com/Getdeck/beiboot-desktop) for end users  of Beiboot, e.g. developers and testers.

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
[codecov-shield]: https://img.shields.io/codecov/c/gh/Getdeck/beiboot?style=for-the-badge&token=QI26A1R5E9
[codecov-url]: https://codecov.io/gh/Getdeck/beiboot


