.. meta::
   :description: Familiarize yourself with contributing to the WordPress charm documentation.

.. _how_to_contribute:

How to contribute
=================

.. note::

   See `CONTRIBUTING.md <https://github.com/canonical/wordpress-k8s-operator/blob/main/CONTRIBUTING.md>`_
   for information on contributing to the source code. 

Our documentation is hosted on `Read the Docs <https://documentation.ubuntu.com/wordpress-k8s-charm>`_ to enable collaboration.
Please use the links on each documentation page to either
directly change something you see that's wrong, ask a question, or make a suggestion
about a potential change.

Our documentation is also available alongside the
`source code on GitHub <https://github.com/canonical/wordpress-k8s-operator>`_.
You may open a pull request with your documentation changes, or you can
`file a bug <https://github.com/canonical/wordpress-k8s-operator/issues>`_
to provide constructive feedback or suggestions.

Developing with Jupyter notebooks
---------------------------------

The tutorial documentation is written in Jupyter notebook, which can be executed in a local environment. 
This allows you to test the code cells, and verify that they work as expected.
The documentation is set up so that Read the Docs renders the code cell output of the Jupyter notebook executed in GitHub Workflows.

For local development of the Jupyter notebooks, you can install [JupyterLab](https://jupyter.org/install) or use the [Jupyter notebook VS Code extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter).

The Makefile targets `make html-with-exec` and `make serve-with-exec` are intended to be used within VMs or containers to execute the Jupyter notebook.
This is intended for developers who want to test the code cells locally in the Jupyter notebooks.
Since the Jupyter notebook documentation often will involve installing software such as Juju, LXD, and Kubernetes, it is recommended to use a VM or container to avoid conflicts with your local environment.
In addition, the installation would need superuser privileges.

The Makefile targets `make html-with-artifact` and `make serve-with-artifact` download the artifacts of the executed Jupyter notebook from GitHub Workflows, and use them to render the documentation locally.
This is intended for developers who want to preview the documentation locally. 
As the executed Jupyter notebook will be used by Read the Docs to render the documentation, this should result in the same output.
To use this target, the commit must be pushed to GitHub and the workflow to execute Jupyter notebook must complete successfully.
In addition, the `GITHUB_TOKEN` environment variable must be set to a valid GitHub token with permission to read the repository and workflows.
As this GitHub token is used to find and download the artifact from the workflow run of the same commit hash.

AI usage
--------

You are free to use any tools you want while preparing your contribution, including
AI, provided that you do so lawfully and ethically. 

Avoid using AI to complete
`Canonical Open Documentation Academy issues <https://github.com/canonical/open-documentation-academy/issues>`_.
The purpose of these issues is to provide newcomers with opportunities to
contribute to our projects and gain documentation skills. Using AI to
complete these tasks undermines their purpose.

If you use AI to help with your PRs, be mindful. Avoid submitting contributions
with entirely AI-generated documentation. The human aspect of documentation is
important to us, and that includes tone, syntax, perspectives, and the
occasional typo. 

Some examples of valid AI assistance includes:

* Checking for spelling or grammar errors
* Drafting plans or outlines
* Checking that your contribution aligns with the Canonical style guide

We have created instructions and tools that you can provide AI while preparing
your contribution in `copilot-collections <https://github.com/canonical/copilot-collections>`_.
While it isn't necessary to use ``copilot-collections`` while preparing your
contribution, these files contain details about our documentation standards and
practices that will help the AI avoid common pitfalls when interacting with our
projects. By using these tools, you can avoid longer review times and nitpicks.

If you choose to use AI, please disclose this information to us by indicating
AI usage in the PR description (for instance, marking the checklist item about
AI usage). You don't need to go into explicit details about how and where you used AI.

Avoid submitting contributions that you don't fully understand.
You are responsible for the entire contribution, including the AI-assisted portions.
You must be willing to engage in discussion and respond to any questions, comments,
or suggestions we may have. 

