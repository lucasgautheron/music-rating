# Music Rating

A PsyNet experiment where participants rate music clips on a scale from 1 to 8.

Participants first complete audio setup and a short forced-choice hearing check.
They then complete 20 music rating trials by default. The static trial maker
targets 5 completed ratings per song.

Generated PsyNet dependency: PsyNet from the GitLab master branch.

## Repository layout

- `experiment.py` defines the PsyNet experiment.
- `static/songs.csv` defines the music stimulus manifest. It must contain
  `track_id`, `pair_id`, `s3_url`, `http_url`, and `is_parent` columns. The
  `http_url` column is used for playback; the other fields are saved with each
  trial for export and analysis.
- `static/hearing_check.csv` defines the audio prescreen sounds.
- `config.txt` contains Dallinger/PsyNet configuration.
- `requirements.txt` pins PsyNet from GitLab.
- `constraints.txt` is present for Dallinger dependency locking workflows.
- `Dockerfile` supports PsyNet/Dallinger SSH deployments.
- `test.py` runs the standard PsyNet experiment test through pytest.
- `.github/workflows/test.yml` runs a basic GitHub Actions test suite.
- `.github/workflows/deploy-hotair.yml` can provision EC2 and start a hotair
  debug deployment from a selected branch.
- `deploy.txt` records the default deployment inputs generated for the workflow.
- `.deploy/ssh/` stores the generated OpenSSH Ed25519 EC2 SSH keypair. This
  directory is intentionally ignored by git.
- `AGENTS.md` links PsyNetSkills guidance for future agent work.

## Local checks

From the repository root:

```bash
python -m pip install --upgrade pip wheel
pip install -r requirements.txt pytest
python experiment.py
```

For full local PsyNet validation, ensure PostgreSQL, Redis, Docker, and the
Heroku CLI are available, then run:

```bash
psynet test local
```

## Prolific Configuration

Prolific recruitment is configured in `Exp.config` in `experiment.py`, with
`recruiter = prolific` and `auto_recruit = false`, so recruitment should be
controlled from the Prolific researcher interface. The current estimate is
14 minutes at $11/hour.

If the number of rating trials or expected trial duration changes, update both
the timing/payment constants and `Exp.config` in `experiment.py`.

## Hotair debug deployment

The generated `Deploy hotair debug experiment` GitHub Actions workflow can be
run manually from the Actions tab. It accepts a branch, tag, or commit SHA to
deploy, plus deployment parameters pre-filled from `deploy.txt`.

Before running it, configure GitHub secrets or repository/environment variables
for AWS:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` if your AWS credentials require one

`psynet-github create` generates a unique OpenSSH Ed25519 EC2 SSH keypair under
`.deploy/ssh/` and, when it creates the GitHub repository, copies the private
key into the `EC2_SSH_PRIVATE_KEY` GitHub Actions secret.
The generated Docker deployment configuration uses GitHub Container Registry at
`ghcr.io/lucasgautheron/music-rating/psynet-experiment-images`.
It also configures `DALLINGER_DASHBOARD_USER` and
`DALLINGER_DASHBOARD_PASSWORD` as GitHub Actions secrets, defaulting to
`admin` / `admin`.
It also installs a local `.git/hooks/pre-commit` hook that rejects staged files
containing private-key PEM/OpenSSH markers.

If this repository was created with:

```bash
psynet-github create lucasgautheron/music-rating --set-aws-secrets
```

then `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional
`AWS_SESSION_TOKEN` were copied from the selected local AWS profile into GitHub
Actions secrets during repository creation.

The workflow checks whether the configured EC2 server already exists, provisions
it with `dallinger ec2 provision` if needed, attempts to stop an existing debug
app with `psynet destroy ssh`, and starts a fresh run with `psynet debug ssh`.

If an existing EC2 server rejects SSH authentication, it was probably
provisioned with a different private key than the current `EC2_SSH_PRIVATE_KEY`
secret. In that case, this workflow intentionally terminates the existing EC2
instance directly, waits for termination, and provisions a fresh server with the
configured key.
Before provisioning, the workflow also deletes any existing AWS EC2 key pair
with the configured `ssh_key_name` so Dallinger can import the public key that
matches `EC2_SSH_PRIVATE_KEY`.
