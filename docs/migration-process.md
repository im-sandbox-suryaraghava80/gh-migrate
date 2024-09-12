# The Migration Process

## Dry-Runs

A dry-run is performed in five steps:
1. Capture a pre-migration snapshot of the source
2. Perform the migration
3. Capture a post-migration snapshot of the source
4. Capture a post-migration snapshot of the target
5. Capture the migration logs

### Pre-Migration Snapshot

Dry-runs typically do not happen within a change or code freeze "window", which means we have to assume the migrated objects are actively being used.

They also typically occur a number of days after the initial "Pre-Migration Analysis" snapshot.

So, to reduce the likelihood of erroneous diff results, we must take snapshots *immediately* prior to execution of the `gh gei migrate-org` commands.

In situations with extraordinarily large organizations, it may be beneficial to re-order the `dry-run.sh` script to take "before" / "after" snapshots immediately before and after *individual* org migrations.

Currently, the tool outputs a script that takes the "after" snapshots after all of the orgs are migrated.

### Migration

The `gh gei` tool support two migration types:
1. `gh gei migrate-repo`
2. `gh gei migrate-org`

The GitHub documentation explains the difference between the two: [link](https://docs.github.com/en/migrations/using-github-enterprise-importer/migrating-between-github-products/overview-of-a-migration-between-github-products#do-we-want-to-migrate-by-organization-or-by-repository)

With proper tooling, the difference between the two types in neglegible.

Here are the differences I can think of apart from what's mentioned in the GitHub docs.

#### Migration Logs

When using `gh gei migrate-repo` with the `--queue-only` option, the migration logs *must* be downloaded **within 24 hours** using the `gh gei download-logs` command.

The migration process also adds a copy of the migration log to each repo, ***but only if the repo has Issues enabled***.

The only way to get clean logs using `gh gei migrate-repo` is if you use `download-logs` within the 24-hour window.

When using the `gh gei generate-script` script, you get noisy logs which can be used in worst-case situations.

`gh gei migrate-org` uses a GitHub API which creates a `gei-migration-results` repository in each migrated org with the logs separated into 'success' and 'failure' folders, so you get guaranteed, long-lived migration logs.