(how_to_contribute_dev)=

# Contribute to development

This document explains the processes and practices recommended for contributing enhancements to the WordPress charm.

## Overview

- Familiarizing yourself with the [Juju documentation](https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/)
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Once your pull request is approved, we squash and merge your pull request branch onto
  the `main` branch. This creates a linear Git commit history.
- For further information on contributing, please refer to our
  [Contributing Guide](https://github.com/canonical/is-charms-contributing-guide).

```{include} contribute_develop.md
```

```{include} ../reuse/contribute/contribute_test.md
```

```{include} contribute_rock.md
```

```{include} contribute_charm.md
```

