# stage-control

[![CI status][ci-img]][ci-url] [![Documentation][doc-img]][doc-url]
[![Version][version-img]][version-url] [![Python][python-img]][version-url]
[![License][license-img]][license-url]

[ci-img]:
  https://img.shields.io/github/actions/workflow/status/bdelwood/stgctl/ci.yml?branch=master&style=flat-square&label=CI
[ci-url]: https://github.com/bdelwood/stgctl/actions/workflows/ci.yml
[doc-img]: https://img.shields.io/badge/docs-stgctl-4d76ae?style=flat-square
[doc-url]: https://bdelwood.github.io/stgctl/
[version-img]:
  https://img.shields.io/github/v/tag/bdelwood/stgctl?sort=semver&style=flat-square&label=version
[version-url]: https://github.com/bdelwood/stgctl/tags
[python-img]:
  https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?style=flat-square
[license-img]: https://img.shields.io/badge/license-MIT-yellow?style=flat-square
[license-url]: https://github.com/bdelwood/stgctl/blob/master/LICENSE

Control software for a pair of Velmex XY stages over serial.

## Installation

Clone the repository and install with [uv]:

```console
$ git clone https://github.com/bdelwood/stgctl.git
$ cd stgctl
$ uv sync
```

## Usage

Please see the [Command-line Reference] for details.

## License

Distributed under the terms of the [MIT license][license-url], _stage-control_
is free and open source software.

## Issues

If you encounter any problems, please [file an issue] along with a detailed
description.

[uv]: https://docs.astral.sh/uv/
[file an issue]: https://github.com/bdelwood/stgctl/issues

<!-- github-only -->

[command-line reference]: https://bdelwood.github.io/stgctl/usage.html
