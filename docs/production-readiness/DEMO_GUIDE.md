# Headquarters demo guide

**AI-assisted Tizen GCC-to-LLVM Image Compatibility Validation** is a 10-minute English demo. In the live run, the candidate deliberately breaks known ELF contracts. The goal is to show that the analysis completed and explained the ABI breaks. The demo uses synthetic RPMs and a real local analysis engine.

- [Slide deck](demo/Tizen_Compatibility_HQ_Demo.pptx)
- [Presenter script and timing](demo/DEMO_SCRIPT.md)
- [Presenter notes](demo/PRESENTER_NOTES.md)
- [Agent prompt](demo/DEMO_PROMPT.md)
- [Expected checks and source of evidence](demo/EXPECTED_RESULTS.md)
- [Historical Raspberry Pi runtime results](demo/RASPBERRY_PI_RUNTIME.md)

## Preflight and live run

Use Linux with Python 3.11+, GCC, G++, RPM, rpmbuild, rpm2cpio and readelf already available. A browser is needed to show the HTML. Choose an existing writable workspace location with at least 256 MiB available. Commands below assume the checkout root as the current directory.

```bash
DEMO="$PWD/docs/production-readiness/demo"
python3 "$DEMO/run_demo.py" --preflight
python3 "$DEMO/run_demo.py" --output "$PWD/demo-live-01"
```

For a separately installed Skill, pass `--skill "/path/to/tizen-image-compatibility"` to both commands. The demo creates a new output directory, builds four RPMs with synthetic ELF payloads, records input SHA256, and invokes the same analysis workflow used by agents. It expects the workflow to exit 1 because of the deliberately detected incompatibilities. The demo runner exits 0 only after its independent checks pass. Open `demo-live-01/report/index.html` and inspect `demo-live-01/report/run-summary.json`.

To show the actual AI interaction, open the company-approved internal AI client with file access to the live run directory. Supply [DEMO_PROMPT.md](demo/DEMO_PROMPT.md), replacing its path fields. If the AI client is unavailable, run the same configuration yourself and label the scene **CLI walkthrough**. Availability and behavior in the internal client require separate verification.

## Backup and rerun

Before the session, generate a second run with `--output "$PWD/demo-backup-01"`. Open its report and verify `demo-receipt.json` reads `"status": "PASS"`. Use that unaltered generated backup if live tools or the internal AI client are unavailable. Label this branch **PREGENERATED SYNTHETIC**. Carry the whole output directory, including the report's `evidence/` directory and CSVs, for offline navigation. Keep the original run receipts.

Rerun with a fresh output such as `demo-live-02`. The runner rejects an existing output. It neither deletes earlier runs nor reuses their results. Fresh fixture bytes can vary across toolchain versions. Judge the rerun using the expected symbol identities, statuses, hashes within that run and report integrity checks.

## Data labels to use on stage

| Label | Meaning |
| --- | --- |
| LIVE SYNTHETIC | Four tiny RPMs built and analyzed in this session. Package metadata and both ELF tables are collected locally. |
| PREGENERATED SYNTHETIC | A real analysis run of the same fixture design that was generated earlier. |
| HISTORICAL DEVICE OBSERVATION | Recorded Raspberry Pi evidence from the earlier validation. The demo does not contact a target device. |
| PRODUCT VALIDATION | Requires independently verified product inputs and execution evidence. A real, approved and redacted report may replace the optional example only when available. |

For large inputs, start with `run-summary.json`, use CSV exports for complete records, and use a bounded browser over an index prepared before the presentation. See the [RPM repository guide](../../.agents/skills/tizen-image-compatibility/references/rpm_repository.md).

## Local rehearsal result

The one-click command generated both live and backup reports from real, locally built synthetic RPMs. The backup used an alternate Skill install, working directory and simulated HOME under the same Linux UID. Paths included spaces and Unicode. Negative rehearsal passed for missing tools and an existing report directory. The original backup `results.json` hash was unchanged after the overwrite refusal.

Chromium showed the missing export and symbol CSV link on the static page. In the optional indexed browser, package filtering showed the provider ELF and the removed symbol. A browser request fetched the original Evidence and verified its SHA256. PowerPoint structure and slide links were verified locally. PowerPoint or LibreOffice presentation playback and the actual internal AI client remain to be exercised on the presentation workstation.
