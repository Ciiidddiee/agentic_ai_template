# 0003: Registry-backed factories and allowlisted entry-point plugins

- Status: accepted
- Date: 2026-10-18

## Context

Components must be selectable from config, and teams need to share extensions (tools, adapters) without forking the kernel. Loading third-party code is a security risk.

## Decision

- **Factory:** one mechanism, the registry. `@register(kind, name)` adds a class or function, and the builder looks it up by the config's `type`. There are no abstract-factory hierarchies and no dependency-injection container. `runtime.py` is the only composition root.
- **Plugins:** standard Python entry points in groups `aikit.<kind>` (one component) or `aikit.plugins` (a module that registers several). A plugin is loaded only if its name appears under `plugins:` in the app config. A listed plugin that isn't installed fails startup.
- **Hooks** provide cross-cutting behaviour but cannot replace the policy, the run loop, or ACL filtering.

## Consequences

- Built-in components and plugins use the same mechanism, so a plugin is indistinguishable from a built-in once loaded.
- Installing a package never changes behaviour on its own, which keeps supply-chain risk visible in config review.
- Plugins should be distributed through the internal package index only.
