> **FOR CODEX ONLY.** If you are ClineSR or another agent, stop: this is not your task.

# WP-3 Addendum A (revision 3): publish the ClineSR VD-1 measurement kit (script revision 4.2)

**Revision 3 note:** your second review is also accepted. Script 4.2 fixes the whole class, not only the two cited lines:

- `TMPDIR`, `TMP` and `TEMP` are exported as `<workspace>/.local-work/tmp` for the script and every child (sort, Python, the tool), and `sort` also gets `-T "$TMPDIR"`.
- Every command in `prepare` that can print RPM paths sends its stderr to `WORK/prepare.private.log`: find, rpm, stat, sort, join, cp, git archive, tar and the selection step. The terminal only shows sanitized `STOP:` lines and counts.
- Copy failures are counted and stop the run with a sanitized message. Unreadable RPMs and find errors are counted.

The PM tested an injected copy failure (sanitized STOP), an unreadable RPM (counted, name only in the private log), too few common names (sanitized STOP), and confirmed that no files were created under `/tmp` during prepare and run.

**Delegated authority (to avoid further round trips):** if your review finds another defect of the *same classes*, meaning writes outside `.local-work/` or package names or RPM paths reaching the terminal, fix it minimally yourself. Then re-run `bash -n` and your smoke test, commit, push, and report the diff and the new sha256. The PM will review the diff afterwards. For any other kind of defect, stop and report.

**Revision 2 note:** your review of the first script correctly blocked it on two points, and both are accepted and fixed in script 4.1:

1. Write confinement is now physical. The workspace and `.local-work` are resolved with `cd -P`. A symlinked `.local-work` is rejected. `WORK` must resolve inside `.local-work`, with no symlink component, and its `base`/`cand` directories must not be symlinks. Report and log files may not be symlinks.
2. `summary` no longer prints raw stderr. It prints only the line count and exception type names, and the stdout status line is cut before the report path.

The PM tested these cases: a symlinked `.local-work`, a symlinked `WORK`, an outside `WORK` path, a symlinked `base`, and a stderr containing a fake package path. Each one stopped or was sanitized correctly. Replace the old `vd1_measure.sh` in Downloads with the new one.

**Priority:** do this **first**, before or in place of WP-3 Step 0 item "copy `CLINESR_VD-1_PROMPT.md`". If WP-3 is already running, do it now as a separate small commit and push. Then continue WP-3.

This addendum **supersedes** every WP-3 instruction about `CLINESR_VD-1_PROMPT.md`. Ignore any revision-3 `CLINESR_VD-1_PROMPT.md` in Downloads; do not copy it.

## Owner rules for ClineSR (record them verbatim in `docs/pm/HANDOVER.md` and `docs/pm/DECISIONS.md`)

1. ClineSR is the Native Server AI. It may download from GitHub but must **never** push, commit or upload anything to GitHub. No prompt may ask it to.
2. ClineSR receives prompts only by the owner's copy-and-paste. Any script or file it needs must be committed to `main` by Codex; ClineSR then downloads it from GitHub.
3. ClineSR's workspace is `/home/liushanshan/Toolchain/Tools/Image-Compatibilty-Skill`, an existing clone of this repository. It must not create any file outside that workspace. Its scratch area is `<workspace>/.local-work/`.
4. `/home/linhao/Downloads` exists only on Codex's PC.
5. The owner relays ClineSR results to the PM.
6. ClineSR's clone currently holds two unpushed local documentation commits made by mistake. Nobody should push or replay them. ClineSR uses `git fetch` plus `git show`/`git archive` only, never `pull` or `merge`.

## Files

| File in Downloads | Put it at | Check |
|---|---|---|
| `vd1_measure.sh` | `docs/pm/clinesr/vd1_measure.sh` (mode 0644 is fine) | `sha256sum` must be `b851c0937e044009da961257fe3c1a2b78668eeb3d370fb91fccad78a49f9068`. Commit it byte-identical unless you use the delegated authority above |
| `WP-3_ADDENDUM_A.md` (this file) | `docs/pm/work-packages/WP-3/ADDENDUM_A.md` | — |

Also:

- Replace `docs/pm/clinesr/VD-1_PROMPT.md` with the text in the section "ClineSR paste prompt (record)" below. It is a record of what the owner pastes.
- Add `/.local-work/` to `.gitignore`.

## Review the script before committing it (read-only)

Read `vd1_measure.sh` and confirm all of the following in your report. If any check fails, do not commit; report instead.

- It writes only under `<workspace>/.local-work/`.
- It never runs `git` commands that change refs or the working tree, other than reading objects. It uses `rev-parse`, `config --get`, `cat-file` and `archive` only.
- It never deletes or modifies the RPM inputs.
- It prints no package names.
- Its two pinned commits, `2d43c58…` and `323e0e1…`, exist on `main`.

Run `bash -n docs/pm/clinesr/vd1_measure.sh`. If `rpm` and `rpm2cpio` are available on your PC, run a smoke test with a few synthetic RPMs. Otherwise report BLOCKED for that part.

## Commit and push

1. Commit only these paths: `docs/pm/clinesr/vd1_measure.sh`, `docs/pm/clinesr/VD-1_PROMPT.md`, `.gitignore`, `docs/pm/HANDOVER.md`, `docs/pm/DECISIONS.md`, `docs/pm/work-packages/WP-3/ADDENDUM_A.md`.
2. Make the verified backup and run `git push origin main`, with no tags and no Releases.
3. Report the pushed commit SHA and the `sha256sum` of the committed script.

## ClineSR paste prompt (record)

```text
FOR CLINESR ONLY — VD-1 revision 4.2 (measurement only, not acceptance)

Rules: Do not commit, push, pull, merge or upload anything. Do not change the RPM folders.
Create files only inside /home/liushanshan/Toolchain/Tools/Image-Compatibilty-Skill
(the script uses .local-work/ there). Run one step at a time. Wait for each step to finish,
then check its last line. If any line starts with "STOP:" or the expected last line is
missing, stop and give me the step number and the last 30 lines.
Do not print or report package names.

Step 1 (download the kit; read-only Git):
cd /home/liushanshan/Toolchain/Tools/Image-Compatibilty-Skill
git fetch origin main
mkdir -p .local-work
git cat-file -e origin/main:docs/pm/clinesr/vd1_measure.sh || echo "STOP: kit not published on GitHub yet"
git show origin/main:docs/pm/clinesr/vd1_measure.sh > .local-work/vd1_measure.sh
sha256sum .local-work/vd1_measure.sh
Expected: b851c0937e044009da961257fe3c1a2b78668eeb3d370fb91fccad78a49f9068

Step 2:
bash .local-work/vd1_measure.sh check
Expected last line: CHECK OK

Step 3 (set the two real repository paths; ask me if you do not know them; may take several minutes):
BASE=/path/to/baseline-gcc-rpms CAND=/path/to/candidate-llvm-asan-rpms bash .local-work/vd1_measure.sh prepare
Expected last line: PREPARE OK WORK=<path>. Copy that path.

Step 4 (long; do not interrupt):
bash .local-work/vd1_measure.sh run <WORK path from Step 3>
Expected last line: RUN OK. Exit codes 0, 1 or 3 inside the output are fine.

Step 5:
bash .local-work/vd1_measure.sh summary <WORK path from Step 3>
Give me the complete output from "VD-1 RESULT" to "END OF VD-1 RESULT", plus anything unexpected.
Keep the WORK directory.
```
