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
    <img src="https://github.com/Schille/beiboot/raw/main/docs/static/img/logo.png" alt="Getdeck Beiboot Logo"/>
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
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#running-getdeck">Running Getdeck</a></li>
        <li><a href="#cleaning-up">Cleaning up</a></li>
      </ul>
    </li>
    <li><a href="#license">License</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About the project
_Getdeck Beiboot_ (or just Beiboot for brevity) was born from the idea to provide Getdeck users a simple yet flexible
solution to spin up **hybrid cloud development** infrastructure. This is useful for development workloads which grew too large to
run on a development machine (or with pony workloads on MacOS and Windows machines).  

### What is **hybrid cloud development**?  
For an efficient Kubernetes-based development workflow it is important to run as many dependant (or attached) services of
the application under development in Kubernetes - even during development time. Almost all the attached services run in a
Kubernetes cluster somewhere in the cloud. However, the application currently under development runs on the developer's machine
and behaves as it would run directly in that Kubernetes cluster.  
The developed application: runs locally - all the rest of the development workload: runs in the cloud = hybrid cloud development.  
Check out [Gefyra](https://gefyra.dev) to see how this works.

### Kubernetes-in-Kubernetes
There are a couple of aspects why a logical Kubernetes cluster running within a physical Kubernetes cluster is beneficial. The
main focus currently is spinning up on demand Kubernetes clusters for development and testing purposes, although Beiboot has potential
for other scenarios, too (e.g. strong workload isolation, multi-tenancy and security).  

Beiboot comes with a Kubernetes operator which handles the ad-hoc logical clusters based on the requested parameters. This includes the
Kubernetes version, the way of exposing the cluster, lifetime and so on.

<div align="center">
    <img src="https://github.com/Schille/beiboot/raw/main/docs/static/img/beiboot-ops.png" alt="Beiboot operator"/>
</div>

The configuration is part of the cluster-key in the [`Deckfile`](https://getdeck.dev/docs/deckfile/specs).

### Built with
Beiboot builds on top of the following popular open-source technologies:

### k3s
[*k3s*](https://rancher.com/docs/k3s/latest/en/) is supported to run local Kubernetes cluster. 

### kind
[*kind*](https://kind.sigs.k8s.io/) is supported to run local Kubernetes cluster. 

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

### Install the operator to the Kubernetes host cluster.
...




<p align="right">(<a href="#top">back to top</a>)</p>

## Usage


<p align="right">(<a href="#top">back to top</a>)</p>

<!-- LICENSE -->
## License
Distributed under the Apache License 2.0. See `LICENSE` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>

## Reporting Bugs
If you encounter issues, please create a new issue on GitHub or talk to us on the
[Unikube Slack channel](https://unikubeworkspace.slack.com/). 

## Acknowledgments
Getdeck Beiboot is sponsored by the [Blueshoe GmbH](https://blueshoe.de). Beiboot heavily relies on the work of [Rancher
k3s](https://rancher.com/docs/k3s/latest/en/).

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


