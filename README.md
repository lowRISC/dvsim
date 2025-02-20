# DVSim

**Note**: *this version of DVSim is an experimental version.
While we have taken steps to try and ensure functional compatibility with the version in the OpenTitan repo.
There will be some differences, mainly to the CLI interface and also to how the working files are managed.*

DVSim is a build and run system written in Python that runs a variety of EDA tool flows.
There are multiple steps involved in running EDA tool flows.
DVSim encapsulates them all to provide a single, standardized command-line interface to launch them.
While DVSim was written to support OpenTitan, it can be used for any ASIC project.

All EDA tool flows on OpenTitan are launched using the DVSim tool.
The following flows are currently supported:

* Simulations
* Coverage Unreachability Analysis (UNR)
* Formal (formal property verification (FPV), and connectivity)
* Lint (semantic and stylistic)
* Synthesis
* CDC
* RDC

# Installation

## Using nix and direnv

If you have [Nix](https://nixos.org/download/) and [direnv](https://direnv.net/) installed, then it's as simple as `direnv allow .`.

New to Nix? Perhaps checkout this [installer](https://determinate.systems/posts/determinate-nix-installer/) which will enable flakes by default.

## Using uv direct

The recommended way of installing DVSim is inside a virtual environment to isolate the dependencies from your system python install.
We use the `uv` tool for python dependency management and creating virtual environments.

First make sure you have `uv` installed, see the [installation documentation](https://docs.astral.sh/uv/getting-started/installation/) for details and alternative installation methods.
There is a python package that can be installed with `pip install uv`, however the standalone installer is preferred.

### macOS and Linux

```console
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
uv sync
```

From there you can run the `dvsim` tool.

### Windows (Powershell)

```console
irm https://astral.sh/uv/install.ps1 | iex
uv venv
uv sync
```

From there you can run the `dvsim` tool.

# Using DVSim

For further information on how to use DVsim with OpenTitan see [Getting Started](https://opentitan.org/book/doc/getting_started/index.html)

# Other related documents

* [Testplanner tool](./doc/testplanner.md)
* [Design document](./doc/design_doc.md)
* [Glossary](./doc/glossary.md)

# Bugs

Please see [link](https://github.com/lowRISC/dvsim/issues) for a list of open bugs and feature requests.
