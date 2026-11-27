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
Expected: ee9b0b6c109f67b9dd27bb70bce053b542364cc7a8f27017382be9a6cdb49a1a

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

## Revision 5

Published script SHA-256 `8bf3dc72b7d2a20b5ac1f98fbd4c7aa77cd9b100c512134b7053dd5a8780af66`. The downloaded revision matched
`16035e63e8b1197bdfe32d59f376da3ba1f4b62ec9a05ed75640844bc41efcdf`.
The delegated privacy and confinement review restricted diagnostic signatures
and file labels, moved new tool streams to private logs, and made rerun logs
exclusive. Existing revision 4.2 WORK remains readable.

```sh
bash .local-work/vd1_measure.sh rerun <WORK> <40-hex-published-commit>
bash .local-work/vd1_measure.sh summary <WORK> 323e0e1 0c40d40
bash .local-work/vd1_measure.sh detail <WORK> <7-hex-tag>
```

## Revision 7

Download the current kit through the same read-only Git workflow. Verify the
published SHA-256 `4a8b6ae5d4442604a36cb2362690d0f344c186ec8a635f58980b9583a84cfb78`.
The source handoff matched
`3effc6819b0b35d1f44c8e0f360e8707a2c61fcb74396df55000f1f4fc846abb`.

Summary skips tags that have no run in the current WORK. Detail reads both
legacy and compressed RC reports and includes export inventory shape,
extraction-error categories, owner-review counts and copy relocation counts.
The local privacy review restricted report keys and values to fixed output
categories and bounded decompressed diagnostic reads. WP-3b, RC1 and the
redaction fixture passed locally. Forward the counts-only output and retain
the private logs on the server.
