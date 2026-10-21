# NEXTSTEP port

Preserve the native OPENSTEP build and keep source changes compatible with
GCC 4.2 (C99/GNU99), even when building with a newer compiler. No browser-engine
modernization belongs in the initial NEXTSTEP port.

Use an explicitly configured Linux-hosted NEXTSTEP toolchain and private 3.3
SDK. Resolve the selected installed toolchain once and record its manifest
hash. Do not hardcode local checkout paths or select historical app-local
compiler bundles. Keep generated sources, dependency inputs, logs and private
configuration under ignored work/. Never commit SDKs, guest images or secrets.

Keep the browser core shared. Use native NEXTSTEP AppKit for the new frontend,
with small shared helpers where useful; do not imitate the entire OPENSTEP
AppKit. Preserve the existing OPENSTEP frontend. Prefer reusable shared
libraries for dependencies. Fix reusable libc gaps in NextStepCompat and
compiler defects in the toolchain, not by hiding them in application shims.

Use disposable guests for runtime tests. Batch focused checks with bounded
waits and explicit result markers. Compilation is not runtime qualification.
Reuse docs/ui-navigation.md and the VM project's navigation notes.
The port plan and current scope are in docs/nextstep-port.md.
