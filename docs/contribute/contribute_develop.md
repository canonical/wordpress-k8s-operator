## Develop

To make contributions to this charm, you'll need a working
[development setup](https://documentation.ubuntu.com/juju/latest/user/howto/manage-your-deployment/manage-your-deployment-environment/).

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/wordpress-k8s-operator
```

Make sure to install [`uv`](https://docs.astral.sh/uv/). For example, you can install `uv` on Ubuntu using:

```bash
sudo snap install astral-uv --classic
```

For other systems, follow the [`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Then install `tox` with its extensions, and install a range of Python versions:

```bash
uv python install
uv tool install tox --with tox-uv
uv tool update-shell
```

To create a development environment, run:

```bash
uv sync
source .venv/bin/activate
```