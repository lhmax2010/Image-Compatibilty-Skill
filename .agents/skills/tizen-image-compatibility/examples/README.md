# Examples

Follow the [Quick Start](../references/QUICK_START.md) to generate two synthetic root filesystems from the included C fixtures. The intentional changes exercise removed symbols, API changes, command removal and coverage reporting. The results describe the fixture.

[synthetic-config.yaml](synthetic-config.yaml) optionally supplies descriptive labels to `tizen_compat.py --config`. Install PyYAML in your Python environment only if you use YAML.

[runtime-workflow.json](runtime-workflow.json) shows the shape of an offline plan for a separately supplied, reviewed bundle. Replace each placeholder with independently obtained local paths and identity values. See [Runtime setup](../references/USER_GUIDE.md#optional-sdk-and-runtime).
