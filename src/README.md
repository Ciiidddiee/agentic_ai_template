# src/

Uses the [src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/): the kernel package lives at `src/aikit/`, so tests and scripts import the installed package rather than whatever happens to be in the working directory.

| Path | Contents |
|---|---|
| [`aikit/`](aikit/README.md) | The reusable kernel: interfaces, components, flows, runtime, CLI, and API |

`aikit` is the default import name. New projects can choose another one when generating from the template (`copier copy`), or later with `python scripts/rename_package.py <name>`.

App-specific code does not belong here. Put it in [`project/`](../project/README.md).
