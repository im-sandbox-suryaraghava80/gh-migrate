# Migration Personal Access Token (PAT)

To perform the steps outlined in the `gh migrate` README.md, Personal Access Tokens (PATs) on the source and target systems need to be created with the following permissions.

Notes
- We do not need “delete_repo” for the source system PAT.
- We use “delete_repo” on the target system to clean-up repos migrated during the dry-run.
- We use “user:email” to help uniquely identify users when mapping them between source and target systems.
- We use "read:enterprise" in target system as it's required by the GitHub migration API


![alt text](docs/images/migration-pat-permission.png)
