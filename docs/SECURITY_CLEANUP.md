# Security cleanup for committed investigation data

The default branch now excludes generated investigation JSON from its current tree. That is not a history purge: older commits, forks, caches, pull-request refs, and other clones may still contain the files.

## Immediate response

1. Temporarily make the repository private in GitHub repository settings while completing cleanup.
2. Review all committed lookup records and test output. Assume any personal data in prior public commits may have been copied.
3. Rotate any credentials that were ever stored in the repository or used alongside these records.
4. Tell collaborators to avoid pushing old clones until history cleanup is complete.

## Purge paths from all local Git history

Coordinate with collaborators first because this rewrites commit IDs. Use a fresh mirror clone and a current installation of git-filter-repo:

    git clone --mirror https://github.com/aryank2212/KAAL_ASE_Release.git KAAL_ASE_Release-mirror.git
    cd KAAL_ASE_Release-mirror.git
    git filter-repo --path data/osint_lookups --path test_api_output.json --invert-paths
    git push --force --mirror

Check the command and target repository before running it. A mirror force-push rewrites branches and tags. GitHub-hosted caches and existing forks/clones may require additional handling, and a history rewrite cannot guarantee removal of copies already downloaded.

## Prevent recurrence

- Generated investigations are ignored under data/; do not force-add runtime output.
- Use .env for all local secrets and keep it out of commits.
- Keep test fixtures synthetic and free of personal information.
- Back up actual investigation output only to private, access-controlled storage with a retention policy.
