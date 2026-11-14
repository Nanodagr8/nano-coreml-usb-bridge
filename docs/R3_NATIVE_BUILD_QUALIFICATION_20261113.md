# Offline native NANO build qualification

The next coding-validation gate is complete: two new isolated workspaces compiled all ten frozen NANO v11 application sources and linked a new ARM64 iOS executable. Both artifacts passed Mach-O structural checks and contain no code-signature load command. This establishes compile/link qualification with existing cached dependencies; it is not a clean dependency rebuild, installable application bundle, deployment or device runtime test.

## Outcome

| Workspace | Native compile/link time | Fresh app object files | Executable bytes | Source/cache unchanged | Network/input isolation |
| --- | ---: | ---: | ---: | --- | --- |
| 1 | 160.454 s | 10 | 13718928 | passed | passed |
| 2 | 168.075 s | 10 | 13718928 | passed | passed |

Both executables are MH_EXECUTE / arm64 for iOS, with minimum iOS 18.0 and SDK 27.1 load-command metadata. The existing Swift compiler reported version 6.4.2. Both compiler argument lists select iPhoneOS27.1.sdk and SDKSettings.json reports version 27.1; the linker metadata must agree. Each compile/link command finished within the locked 180-second deadline. The worker hashes the original cached input tree before and after; both runs used the same unchanged tree.

These times are qualification diagnostics, not an AI-offloading benchmark. No AI requests ran in this gate, and no comparison with the earlier typecheck timings is valid. The original qualification attempt timed out at 180 seconds and its two-job plan stopped after that first failure. Its artifact was not accepted: the process exit was unsuccessful and the linker advertised SDK 18.0 despite compiler inputs selecting SDK 27.1. The [failed attempt](../results/r3_native_build_attempt1_failed_20261113.json) and [original plan](../results/r3_native_build_qualification_protocol_20261113.json) remain visible. Revision 2 disables debug-info output and explicitly passes the verified compiler SDK version to the cross-linker, retaining the same 180-second deadline and artifact requirements. Its two commands run in new workspaces; they are not retries of an unchanged configuration or pooled performance observations.

## Isolation and evidence

- A local plan and runner SHA were locked before execution; there was no public preregistration or statistical hypothesis test for this build-validity gate.
- Existing source hashes and dependency-lock bytes match the prior frozen ten-source specification. The package definition must match this checkout.
- Stale app objects, linked binary, module outputs and module caches are moved aside only inside the new workspace. All ten source object mtimes and the binary mtime must follow command start.
- An additional link-file-list audit verifies that all ten newly compiled app objects, and no prior app objects, were linked.
- The build runs in private Linux mount and network namespaces. The prior cache project, SDK directory and toolchain are read-only mounts. The new network namespace has only loopback.
- SwiftPM automatic resolution is disabled. HOME, shared cache, config and security paths point into the new private workspace. The compiler runs under the existing unprivileged build identity.
- A watchdog kills the owned process group on timeout. Existing source/cache bytes are rehashed after the process exits.
- SwiftPM debug-info-format is none. The linker receives an explicit platform_version ios 18.0 27.1 and -no_adhoc_codesign; the artifact parser independently rejects any LC_CODE_SIGNATURE.
- Only scalar evidence and hashes are published. Private configs, command logs, dependency cache, SDK, executable and signing assets are not included.

[Locked plan](../results/r3_native_build_qualification_protocol_v2_20261113.json), [numeric evidence](../results/r3_native_build_qualification_20261113.json), [runner](../client/r3_native_build.py), and [audit tests](../tests/test_r3_native_build.py).

## Reproduce with an existing authorized cache

The runner defaults to a dry plan:

```text
python client/r3_native_build.py
```

For live qualification use an existing Linux/WSL Swift 6.4.2 setup with the matching iOS SDK, locally cached compatible dependencies, the frozen source tree and an existing SwiftPM executable wrapper. No tools or SDK are installed by this runner.

Create a private JSON configuration outside the checkout, with exactly these fields:

- workspace: a new absolute Linux directory outside the checkout and input project.
- cached_project: an existing project containing matching Sources/NanoANEBridge, Package.swift, Package.resolved, .build and xtool/.xtool-tmp/{Package.swift,Sources}.
- swift_bin: the existing Swift toolchain usr/bin directory.
- swift_sdks: the existing Swift SDK artifact-bundle directory.
- uid and gid: an existing unprivileged Linux build identity that can read the toolchain and SDK.

Invoke under already-authorized Linux namespace privileges:

```text
python3 client/r3_native_build.py --execute --config /private/native-build-config.json
```

The runner requires a new workspace, at least 2 GiB free, compatible preexisting cp/unshare/mount/setpriv utilities and the existing SDK/cache. It refuses overwriting the workspace. Keep result.json and build.private.log private until auditing them; the log contains machine paths. After a failure, preserve the attempt and investigate instead of silently retrying.

## Limits

This uses a dependency cache copied from a prior working application build, so it does not establish a clean-room source build of all third-party dependencies. Two runs share the same host, cache lineage and toolchain; they are not independent external reproduction. A compiler binary and cached-tree digest are recorded, but all SDK/toolchain binary contents are not individually attested.

Native compilation and linking do not validate app resources, entitlements, provisioning, Apple signing, installation, foreground wake-lock behavior, TLS runtime behavior or model inference. The separate dirty iOS wake-lock edits are excluded. No performance, GPU, ANE or energy advantage is claimed. The earlier two-session typecheck/AI study remains separate and unchanged.
