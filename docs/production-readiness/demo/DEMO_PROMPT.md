# Copy into the company-approved internal AI client

> Use the installed Tizen Image Compatibility Skill to compare the baseline RPM repository at **BASELINE_PATH** with the candidate at **CANDIDATE_PATH**. My goal is to validate Export Symbols from the actual payload ELF files. Use the built-in workflow, no custom analysis code. Keep all inputs unchanged and write the run to the new directory **OUTPUT_PATH**. This is offline synthetic data. Run the workflow plan and then the analysis. Start your answer from the machine-readable summary. Give me the objective completion, execution, compatibility and coverage statuses separately. Show the relevant package, provider ELF and consumer import for `legacy_export`. Include paths to the original report or evidence and say what remains UNKNOWN. Avoid reading the full JSON report when its size is large.

For a rehearsal with an already completed run, replace the run instruction with “Read the completed workflow from **OUTPUT_PATH** and answer the same questions.”

For the zero-network demonstration use only local paths from a generated fixture. The workflow configuration keys are `baseline`, `candidate`, `output`, `objective: EXPORT_SYMBOLS` and `rpm_mode: payload`. The production acceptance matrix tracks real company-agent execution separately.
