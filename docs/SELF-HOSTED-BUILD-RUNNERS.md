# Beacon: verified builds using trusted self-hosted GitHub Actions runners

## Why this exists

Beacon's private-repository GitHub-hosted Windows, Linux, Android and backend runs have failed **before any runner starts**, reporting zero executed steps. This is an infrastructure/account-level release blocker; editing Go source or Gradle options cannot resolve a job that never reaches the compiler.

**Nothing in these instructions skips any test, packaging step or artifact check.** They connect alternative trusted build machines to the **same GitHub Actions workflows**, enabling real builds to finish. The workflows still fail if source doesn't compile or tests fail.

Self-hosted runners use machines you administer; GitHub's current Actions billing documentation says runner compute itself is free, while artifact/storage and other account constraints can still matter. Be mindful of the user's $0 third-party service requirement. No paid runner is necessary.

## Two dedicated build workstations

1. **Windows x64 builder:** Windows 10/11, network access, enough disk, used for the actual Go/Fyne Windows EXE.
2. **Linux x64 builder:** a separate Linux VM or nonproduction workstation with normal access to GitHub, Go module proxy, Android SDK downloads and system build dependencies. Handles the Go/Fyne Linux binary, Android APK, and the Docker/server CI (requires a working Docker daemon).

For security, **do not install an unrestricted self-hosted Actions runner on the production Dokploy/Docker admin host**. GitHub job steps execute repository code and third-party actions with runner-host privileges. Use a dedicated, replaceable and isolated build machine/account. Treat pull requests as untrusted and restrict workflow execution/access accordingly. Do not store Dokploy, production DB, GitHub PAT or other credentials in the runner host.

## Registration (the repo owner must authorize this)

In the private [Beacon repository](https://github.com/gigabytegrove/beacon), go to:

**Settings → Actions → Runners → New self-hosted runner.**

Register the **Windows** runner using GitHub's displayed Windows/x64 install and configuration commands, with one additional custom label: `beacon-windows`. Retain the default `self-hosted`, `Windows` and `X64` labels.

Register the **Linux** runner using the Linux/x64 instructions, with custom label: `beacon-linux`. Retain `self-hosted`, `Linux` and `X64`.

Prefer a dedicated low-privilege OS account. Only the owner should handle the registration token, and it must **never** be posted in chat, issue comments, screenshots, logs or the repository.

Verify both runners appear **Online** in the repository's Runners tab, with the exact labels.

GitHub's documentation: https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow

## Prerequisites on the build workers (not end-user PCs)

**Windows:** a working Go-compatible toolchain, MSYS2 MinGW-w64 GCC, PowerShell and the GitHub runner. The Windows workflow uses `msys2/setup-msys2@v2`, `actions/setup-go` and the checked-in `scripts/build-desktop-windows.ps1`. Build output is `Beacon-Windows-0.8.0.exe` with SHA-256. Users of the final binary do not need Go, Python or MinGW.

**Linux:** a working Docker daemon for server CI and an x64 Linux desktop build environment. Install `gcc`, `pkg-config`, `libgl1-mesa-dev`, `xorg-dev`, `libxkbcommon-dev` ahead of time and provide permission to run Docker on this dedicated builder. The workflow validates the installed graphics libraries, runs Go API tests, and builds `Beacon-Linux-0.8.0.tar.gz`.

**Android:** the Linux workflow uses `actions/setup-java`, `android-actions/setup-android`, `gradle/actions/setup-gradle` and `sdkmanager` to install Android SDK 35 and build the native Java app. Expected artifact: `Beacon-Android-0.7.0-debug.apk`.

Use **network access and storage on the build machines** to download dependencies and SDKs. These are build-time, not end-user, prerequisites. Do not manually skip the tests to get a green badge.

## Enable the exact same workflows

There are two methods; no code changes are needed after runner registration.

**One-run test (recommended first):** Open the repository's **Actions** tab, choose one workflow, click **Run workflow**, select branch `main`, and set **Runner location: self-hosted**. Repeat for the server CI, Linux Go, Windows Go and Android workflows. Their outputs still require successful execution and valid artifacts.

**Make the self-hosted workers the default for *push* CI:** Under **Settings → Secrets and variables → Actions → Variables**, add a *repository variable*:

`BEACON_USE_SELF_HOSTED_RUNNERS=true`

When that variable is `true`, all four workflows route pushes and manual runs to the labeled self-hosted machines. When absent or set to anything else, they remain GitHub-hosted by default. Manual workflow dispatch can also select self-hosted without changing the variable.

If a job remains queued, check both **Online** and runner labels; it will not skip execution because a compatible runner is unavailable.

## Mandatory release results

All four workflows must complete, not merely start:

- **Beacon CI:** Python/FastAPI tests pass, JavaScript syntax check passes, Docker image builds.
- **Beacon Go Windows Client:** Go transport tests run, Fyne EXE builds and is uploaded with SHA-256.
- **Beacon Go Linux Client:** Go transport tests run, Linux binary packages successfully and checksum verifies.
- **Beacon Android Build:** Gradle compiles the native Java Android app and uploads a nonempty APK.

Then **install and run** each binary on a matching device and verify two users can sign in, send/receive, receive typing/online alerts, view buddy photos, use device controls, and recover after disconnect. Green CI alone is not a substitute for runtime acceptance.

This path addresses the **runner availability problem**, not an application compiler defect. If compilation fails once a real runner executes, fix the compiler/test error and retry—do not bypass the failed job.

## Restore GitHub-hosted runners independently

Self-hosted execution does **not** repair an account's GitHub-hosted runner billing/eligibility issue. Separately inspect the owner account's **Billing and licensing → Actions / budgets / spending limits** and the repo's **Settings → Actions → General**. Contact GitHub Support if hosted jobs continue reporting immediate startup failures even though the account should be eligible.

See [Build and Test](BUILD-AND-TEST.md), [Release Checklist](RELEASE-CHECKLIST.md) and [Runner Recovery](GITHUB-ACTIONS-RUNNER-RECOVERY.md).

## Pull-request isolation and artifact retention

For safety, even when `BEACON_USE_SELF_HOSTED_RUNNERS=true`, **`pull_request` events continue targeting GitHub-hosted workers**, never your personal self-hosted machines. Owner-approved `push` and `workflow_dispatch` events can use the isolated workers. Review and merge PRs before building on them with your own hardware; do not expose local runner privileges to untrusted PR code.

Build artifact retention is set to **7 days** to reduce storage costs. Download and verify binaries within the retention window. GitHub Actions/artifact storage policies are separate from the cost of computing on your own runners.
