# Ten-minute presenter script

| Time | Slide or live action | Presenter cue |
| --- | --- | --- |
| 0:00–1:00 | 1. Purpose | “What would break when existing consumers move to a new Tizen build? Today a deliberately altered synthetic package answers that question at the binary-interface level.” |
| 1:00–2:00 | 2. Workflow | “The agent captures intent. A local Python engine makes the decisions. Package identities and ELF observations remain separate from device proof.” |
| 2:00–3:00 | Open the company agent with the prepared prompt | Show baseline and candidate locations. Ask for export comparison. Allow the agent to plan and run on fresh paths. If you ran one-click preparation first, ask the agent to summarize the completed run. |
| 3:00–4:00 | 3. Evidence and generated inputs | Show the fixture receipt and report homepage. Point out the repository scope, two extracted archives and two collected ELF objects per side. The payload names do not end in `.so`; the engine recognizes ELF content. |
| 4:00–6:00 | 4. Follow the symbol changes | Open `packages.csv`, locate `demo-codec`, follow its package ID into `elf-symbol-summary.csv` and then `symbol-differences.csv`. Show the missing export, added export, changed version and data size, and the function-only code size change. |
| 6:00–7:15 | 5. Consumer and provider | Show `demo-client` from the IMPORT row for `legacy_export@DEMO_1`. Show the provider's original export `legacy_export@@DEMO_1` and the missing candidate row. Open its content-addressed Evidence. Explain why a package archive does not establish which physical provider a running device loads. |
| 7:15–8:15 | 6. Completion and coverage | Open `run-summary.json`. The requested export objective completed. Confirmed static ABI breaks exist. Installed loader/runtime evidence remains outside this run. Show the evidence references and the exact scope label. |
| 8:15–9:15 | 7. Real device boundary | Give the historical Raspberry Pi summary. Name the target profile and tested sample scope. Explain the pending matching VD reference and headless matrix. |
| 9:15–10:00 | 8. Repeat it | Point attendees to the local demo command, configuration, report and known gaps. Invite them to reproduce the run with new output. |

Use the unaltered pregenerated run if needed. Return to slide 4 and identify the backup explicitly as **PREGENERATED SYNTHETIC**.
