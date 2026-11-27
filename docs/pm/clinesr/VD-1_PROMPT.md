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
