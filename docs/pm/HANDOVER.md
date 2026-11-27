# PM handover

Start with [PM_STATE.md](PM_STATE.md), [DECISIONS.md](DECISIONS.md), [CODEX_STATE.md](CODEX_STATE.md), and the [issue register](ISSUE_REGISTER.md). Then read the [WP-1 prompt](work-packages/WP-1/PROMPT.md) and the [VD-1 prompt](clinesr/VD-1_PROMPT.md). WP-1 starts from local main 69914261a7d4913230ac5a3c29734c78aa64ff8b, whose parent is the review baseline 2d43c58b8753c53f58fae906cc4c821bd6227397. Compare the live checkpoint and actual Git state before resuming.

The open work is WP-1 through WP-6 and VD-1/VD-2. Clause dependencies and owners are in the issue register. Claude independently reviews commits, evidence and acceptance. ClineSR performs VD workstation work.

## Verify the latest PM backup

From the repository root, run:

```sh
backup=".local-backups/$(cat .local-backups/LATEST)"
(cd "$backup" && sha256sum -c SHA256SUMS)
git bundle verify "$backup/main-and-tags.bundle"
```

Restore into a fresh directory under the workspace. The bundle contains committed history and local tags. The other archives preserve the PM docs and untracked inputs, and the patch files preserve staged and unstaged differences. Reconcile the restored state before applying those patches. The normal push of main backs up committed PM continuity material.

## ClineSR owner rules

1. ClineSR is the Native Server AI. It may download from GitHub but must **never** push, commit or upload anything to GitHub. No prompt may ask it to.
2. ClineSR receives prompts only by the owner's copy-and-paste. Any script or file it needs must be committed to `main` by Codex; ClineSR then downloads it from GitHub.
3. ClineSR's workspace is `/home/liushanshan/Toolchain/Tools/Image-Compatibilty-Skill`, an existing clone of this repository. It must not create any file outside that workspace. Its scratch area is `<workspace>/.local-work/`.
4. `/home/linhao/Downloads` exists only on Codex's PC.
5. The owner relays ClineSR results to the PM.
6. ClineSR's clone currently holds two unpushed local documentation commits made by mistake. Nobody should push or replay them. ClineSR uses `git fetch` plus `git show`/`git archive` only, never `pull` or `merge`.
