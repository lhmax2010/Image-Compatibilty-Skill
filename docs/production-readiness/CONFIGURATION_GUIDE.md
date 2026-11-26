# Configuration guide

Copy [workflow.json](../../.agents/skills/tizen-image-compatibility/examples/workflow.json), update the input paths and choose a new output directory. The [bundled workflow guide](../../.agents/skills/tizen-image-compatibility/references/workflow.md) lists each field and exit code.

| Setting | Effective source |
| --- | --- |
| Input, output and required objective | Job JSON. Relative paths are anchored to the directory containing that JSON |
| Collection, tool overrides and CI policy | Optional trusted engine YAML over built-in defaults. The workflow resolves legacy relative engine paths from its YAML directory |
| Legacy static CLI | Explicit command-line flags take precedence over engine YAML. Legacy relative paths are anchored to the invocation directory |
| SDK/sysroot, compiler, device enrollment and trusted Runtime config | Explicit existing SDK and Runtime CLIs. Keep each product/profile and SHA256 separate |
| Cache | Optional account-private directory. Jobs can reuse a compatible cache owned by the same trusted account |
| Report HTTP port | Explicit `enhance_report.py serve --port N`. Use port 0 for automatic loopback assignment |

The workflow rejects unknown and duplicate JSON keys, overlapping output/cache/index locations, and unconfirmed RPM fallback. Engine configuration rejects unknown sections and validation errors. Read-only `doctor` and `plan` do not acquire tools, unpack packages or invoke target programs. Optional indexing has an independent status.

The operator provides compiler paths, SDK roots, build identities, the SDB endpoint and report ports. Use the approved company credential store or preauthenticated transport. Keep credentials outside workflow or engine files. Reports and raw tool logs can contain internal paths and evidence. Keep them in a trusted location.

Use distinct report and index directories for concurrent sessions. A run claims its output directory and keeps its reservation with its evidence. Choose a new output name after interruption. Configure host job limits and disk quotas for a shared production worker. [Side-effect review](SECURITY_AND_SIDE_EFFECTS.md)
