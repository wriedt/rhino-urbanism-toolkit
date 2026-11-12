# Preparing the beta plugin

`release.json` selects the beta version. The current review candidate uses
`0.1.0-beta1`; RhinoCode appends a build identifier. Dotted prerelease labels
are truncated by the tested builder, so do not substitute `beta.1`.
`Build.ps1` builds and verifies the candidate; `python packaging/build_release.py`
then assembles a new immutable review folder/ZIP under ignored `release/`.
It includes only the plugin, standalone toolbar, install/remove helpers,
START_HERE.txt, GPL license and the source needed to build it. Development
documents, tests, feedback forms, release notes and status/checksum reports stay
outside the ZIP. Verification results remain in build/work. It never publishes.
The generated `build/release-kit.json` identifies the exact output.

The existing rhproj keeps its plugin ID. Its 18 generated command wrappers have
stable IDs, explicit Python 3, the approved light/dark SVG icons and command-help
links. One toolbar is titled **RUT | Rhino Urbanism Toolkit**. Three native
separators divide its 18 buttons into **Layers**, **Blocks**, **Floor Area** and
**Curve Tools**, in that order.

Run `python packaging/prepare.py` before building or after changing source files,
icons or help. It copies only the agreed command scripts and helpers into the
generated `build/stage/rut_runtime/` library, refreshes wrappers and the rhproj, and
writes `build/stage/inventory.json`. Do not edit staged copies. Do not add the
repository root as a library: that would distribute tests and work material.

Build through the repository wrapper so the visible title and categories are
applied both to the RUI and to the toolbar inside the Yak package:

```powershell
./packaging/Build.ps1 -PythonExe python
```

`toolbar_layout.json` is the category/order definition. `finish_toolbar.py`
organizes the generated toolbar without changing the plugin/package filename or
IDs. If building directly through Rhino's Script Editor or RhinoCode CLI, run
`python packaging/finish_toolbar.py` afterwards before installing or sharing.
The single toolbar tab uses the full plugin name. Native-container import remains a development
experiment and is excluded from the package after an unresolved Rhino crash
during automated floating-window placement. See the phase 4 follow-up.

Rhino 8.36 is the initial validation target, based on existing recorded tests;
it is not yet an installed-package compatibility claim. The preparation script
does not publish, install, change aliases or touch model geometry.

Commands import `rut_runtime.rut_bootstrap`, not a top-level bootstrap module.
The staged library includes `__init__.py` so Rhino deploys it as an importable
Python package. The generated runtime library includes the real script files so existing
`__file__`-based loading and helper reloads can work after deployment. Thin command
wrappers pass Rhino's injected document to the bootstrap, which restores the
previous script context afterwards. The runtime library must be validated in an
installed build, including coexistence with source scripts and modeless windows.

## Local aliases

Run `packaging/audit_aliases.py` in Rhino's Python 3 Script Editor. It prints
existing aliases with the same names as packaged commands and their exact macros.
It changes nothing. Keep a copy of that output before disabling any conflicts in
Rhino Options > Aliases for the installed-package checks. Restart Rhino when
switching between source development and installed-package testing to clear
cached modules. Existing direct source-file buttons remain unchanged.

## Help and distributed content

The allowlist includes the GPL license and Markdown command help as package
resources. Command Help URLs point to the matching repository documentation;
new help must be present on the selected release branch before distribution.
Installed offline resource paths and toolbar display are phase 4 checks.

The builder adds build metadata to the beta version. Use `8.36-win` as the CLI
target: the installed Rhino builder did not interpret `8.36-windows` as a Windows
restriction. The project itself also specifies the Windows target.

Reference: https://developer.rhino3d.com/guides/scripting/projects-create/

Phases 3 and 4 still gate reliability and installed-package behavior. Preparing
or building the project does not admit conditional tools to the beta automatically.

## Preparation verification

After preparing and building:

```powershell
python packaging/test_packaging.py
./packaging/Verify-Build.ps1
```

Five Python checks cover the staged dependency closure, exact source copies,
injected document context, cleanup on failure and path containment. The current 113
build-content checks cover the generated toolbar actions, exact theme SVGs,
embedded scripts/library allowlist, Windows target and the Yak file allowlist.
The latest results are in PHASE6_RELEASE_REVIEW.md. These checks do not exercise Rhino modeling behavior.

The Windows-only build outputs are under `build/rh8_36-win/`. Older exploratory
builds under `build/rh8_36/` are not the candidate to use for installed testing.

## Installed validation

`Install-Isolated.ps1` uses the native Yak client with a dedicated PackageFolder
under `work/phase4-validation/`; `-Remove` removes only this test installation.
Its manifest selects the active version rather than whichever version directory
sorts first. The isolated Rhino scheme is `RUTBetaValidation`. Probe, smoke and
lifecycle scripts target that process explicitly using RhinoCode's `--rhino`
option. Never run them against a working drawing or add the repository to that
process's module search path.

The runtime library must be a Python package: `rut_runtime/__init__.py` is
required, and wrappers import `from rut_runtime import rut_bootstrap`. The initial
top-level bootstrap import built successfully but failed in Rhino. The corrected
layout passed installed dispatch, source-access blocking and restart checks.

See [the validation record](../PHASE4_VALIDATION.md) for the scope of package
installation testing, successful automatic discovery and the remaining clipboard
hands-on check. `Test-StandardInstall.ps1` refuses to modify an existing normal
RUT installation and requires a test-owned marker before removing its temporary
installation. Never leave that trial installed after the discovery process exits.
