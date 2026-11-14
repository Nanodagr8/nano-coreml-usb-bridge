# Reproduce the NANO coding-validation research

This package measures a fixed Swift typecheck of ten frozen NANO v11 sources while two short, exact-answer AI requests run on Windows CPU, Windows GPU, or a foreground physical iPhone. Windows controls the existing compiler through WSL. It does not package, sign, install or deploy an app, and it does not evaluate generated code quality.

## Inspect and recompute without devices

With the existing Python test dependencies available:

```text
python -m unittest discover -s tests -v
python client/r3_application_study.py
python client/r3_application_analyze.py results/r3_application_session1_20261113.json
python client/r3_application_analyze.py results/r3_application_session2_20261113.json
```

The study command defaults to a dry plan; it starts no compiler or phone requests. The analyzer uses only the standard library. Protocol JSON files preserve exact registered bytes through Git attributes. The source specification instead uses canonical sorted-key, compact ASCII JSON hashing, allowing harmless formatting differences.

The [source specification](../results/r3_application_source_spec_20261113.json) identifies all ten source hashes, Git commit, exact argument template, Swift version, SDK basename and dependency-lock hash. The public runner was used in session 2. Session 1 used a private predecessor; its numeric evidence and frozen protocol are retained separately. Source identity is equivalent through the public template, not by equating the two private physical path manifests.

## Prepare an authorized existing environment

No dependencies, model weights, Apple SDK, certificates or signing assets are distributed here. Use an already trusted Swift 6.4.2 compiler, iPhoneOS27.1 SDK, compatible precompiled dependency modules and the matching dependency lock. Version strings and the lock do not prove binary identity of SDK/compiler/module contents. A different environment is a new reproduction and should disclose its differences.

Obtain the frozen public source commit 8e2087e4ff838970e2346e6520be87af8b9aed7c and provide its ten Swift files as a source tree. Keep private configuration, workspace, logs and reports outside this checkout. The preparer runs under Linux/WSL and accepts an external JSON configuration with:

- workspace: a new absolute Linux workspace path.
- source_tree: the directory containing the ten matching Swift files.
- dependency_lock_file: an existing matching dependency lock.
- paths: absolute existing Linux paths named compiler, dependency_modules, yyjson_module_map, yyjson_headers, swift_resource_dir, toolset_bin, sdk and platform_swift_lib.

```text
python3 client/r3_swift_prepare.py --config /private/materialization.json
```

It validates the source and lock, creates a new private source/cache workspace and writes job.json. It executes no build or installation. Keep job.json private because it contains machine paths. Record the returned physical manifest SHA and logical specification SHA. The logical specification must match the protocol.

On Windows, set NANO_R3_PRIVATE_DIR to a new private output folder and NANO_SWIFT_STUDY_CONFIG to an external JSON file containing exactly:

- job_manifest_linux: Linux path of the new job.json.
- job_manifest_sha256: its SHA-256.
- linux_runner: WSL-visible path to client/r3_swift_job.py in this checkout.
- linux_phase_root: WSL-visible path of the same Windows output folder.
- wsl_distribution: the installed WSL distribution name.

The existing pinned USB tunnel, foreground NANO service, protected NANO_USB_TLS_PIN and NANO_USB_BEARER, and local Ollama model/placement checks must already work. Load secrets locally; never put them in a shell transcript, configuration committed to Git, or reports. The worker removes NANO_USB_* from compiler subprocess environments.

## Run a separately registered reproduction

First register your environment, seed/order, calibration count, outcomes and stopping rules. Do not overwrite the published protocols. The provided runner reproduces session 2's fixed order and rules; --reproduce permits different physical paths while preserving the same logical source/argument specification.

Use five fixed unmeasured cache-calibration jobs, retain their outcomes, and do not pool them with measured jobs. The cold cache can approach the 45-second deadline. Each of the 25 measured jobs also gets one immediately preceding unmeasured compiler warmup. There are 36 AI warmups and 36 measured requests, with no automatic retries or outlier removal.

```text
python client/r3_application_study.py --execute --reproduce --report PRIVATE_OUTPUT/session-report.json
```

Use an absolute report path directly inside the private output folder. On failure, retain the failed attempt and stop; a recovery requires a separately declared new attempt. The compiler owns a 45-second process-group watchdog. The controller checks the 600-second run budget between conditions; the individual watchdog bounds a condition already started near that limit. The run is foreground supervised and bounded.

The overlap check requires both AI requests to finish at least 0.25 seconds before the conservative earliest compiler finish, using Windows launch-relative offsets and Linux compiler duration without equating OS clock epochs. This establishes process overlap, not ANE execution or energy savings.

Public evidence uses an explicit scalar allowlist. Preserve raw reports privately, publish only audited fields, and compare protected credential values locally before publication. Conditional paired-round bootstrap intervals cover only an exchangeable-round resampling model within a session; they do not establish between-session, cross-machine, thermal or causal uncertainty.
