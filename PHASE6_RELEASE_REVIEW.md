# Phase 6 — beta 1 release review

Status: **technical preparation complete; final acceptance/sharing not authorized**.

The agreed command list is 18 uppercase RUT commands, including PushPullCurve and
ShapeBuilder after Rune's reported hands-on pass. The UI uses one **RUT | Rhino
Urbanism Toolkit** tab and three category separators. The modeling runtime is
unchanged during release preparation.

Release materials: [release notes](BETA_RELEASE_NOTES.md),
[quick start](BETA_QUICK_START.md), [feedback form](BETA_FEEDBACK.md), offline
command help, GPL license, matching source archive, local Yak installer, optional
standalone toolbar and install/remove helpers. Exact artifacts and checksums are
recorded in the generated release kit and `build/release-kit.json`.

## Candidate and verification

The candidate is **0.1.0-beta1+20601**, targeting Windows / Rhino 8.36 or later.
The exact version includes RhinoCode's build identifier; `beta1` is used because
the builder truncates a dotted prerelease label such as `beta.1`.

- 113 build-content checks passed, including the 18 uppercase commands, three
  separators, exact light/dark icons, runtime allowlist, standalone toolbar and
  all 13 packaged help/license resources matching their source files.
- All five packaging tests passed. The modeling runtime is unchanged from the
  earlier reliability checks and Rune's reported hands-on pass.
- A temporary normal-folder installation was discovered automatically by a
  fresh Rhino process, with no explicit plugin load. The assembly and libraries
  loaded from the **0.1.0-beta1+20601** installed folder, not the checkout.
- All 18 commands were registered; the validation profile had no RUT aliases.
  Two immediate layer commands dispatched successfully. Checkout Python access
  was blocked; an installed-library test measured 80 m² base and section.
- The actual packaged `RUT.rui` opened as one full-name toolbar and was visually
  checked with all 18 icons and three dividers. No container import/maximizing
  was used. The empty validation document stayed unchanged; clipboard access
  was not used.
- The temporary review process was closed and its normal-folder installation
  removed. The test-owned marker confirms that the previously absent package
  folder is absent again. User drawing windows and source aliases were untouched.

Evidence: `work/phase6-validation/package-probe.json`,
`work/phase4-validation/temporary-standard-install.json`, and the build's
`preparation-checks.json`. The kit assembly verifies the final ZIP against its
per-file SHA-256 inventory. Helper-script guards are checked separately.

## Crash investigation

Windows Application events show two exceptions in process 13708 during the same
floating-toolbar setup incident: 0xe0434352 at 10:41:50 and 0xc000041d at
10:41:58 on 2026-11-12. The preserved WER archive contains Report.wer only; the
listed temporary dumps are no longer present. No retained RhinoDotNetCrash report
was found in the test-session folders. These records establish a crash, not its
root cause. No RUT modeling command was active. Other machine-wide plugins were
loaded, so the failure cannot be attributed conclusively to Rhino or RUT.

Custom native-container import and automated floating-toolbar maximizing are
excluded. Ordinary RUI toolbar opening is the beta's fallback. This is a scope
restriction, not a confirmed crash fix. The release notes retain the unresolved
issue for Rune's acceptance decision before sharing.

## Approval boundary

Phase 6 prepares a concrete candidate for review. Rune still needs to accept the
final command list and documented limitations, then authorize sharing. Phase 7
requires the invited testers/destination to be chosen. No commit, public upload,
GitHub release, Yak publication or message to colleagues is part of this work.
