# Workspace and Git rules

- Only create, modify or delete files inside this workspace. Writing outside it requires the user's explicit exception, including temporary files, logs, caches and backups. Keep tool outputs and temporary directories inside the workspace.
- Do not create, update, merge or otherwise operate on GitHub pull requests. Upload repository content only through ordinary `git push`, when the destination and upload are authorized. Do not force-push.
- Before changing Git remotes or migrating repositories, preserve local branches, fetched remote branches, tags, staged state and uncommitted/untracked work in a verified workspace-local backup. Fetching does not authorize merging or discarding local changes.
- Keep `.local-backups/`, credentials, private local inputs, generated caches and large analysis outputs out of publication. Use exact reviewed paths when staging; do not use blanket `git add -A`.
- Preserve source, permanent tests, small required fixtures, documentation and relevant PM evidence. Historical review evidence is not disposable merely because it is old. Clean only demonstrably regenerable or unnecessary files, after preserving valuable work.
- Follow [the publication policy](docs/PUBLICATION_POLICY.md) for the new private repository. Do not change a remote or push until the user supplies and authorizes the destination.
