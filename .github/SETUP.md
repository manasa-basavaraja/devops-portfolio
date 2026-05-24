# GitHub Actions Pipeline Setup

This repo uses a GitHub Actions workflow defined in `.github/workflows/pipeline.yml`
that runs **secret-scan → terraform init/plan → terraform apply** for the Terraform
code in `terraform-aws-etl-pipeline/terraform/`.

## 1. Required repository secrets

Add the following secrets in **Settings → Secrets and variables → Actions**:

| Secret name             | Purpose                                          |
| ----------------------- | ------------------------------------------------ |
| `AWS_ACCESS_KEY_ID`     | IAM access key used by the workflow              |
| `AWS_SECRET_ACCESS_KEY` | Matching secret access key                       |

(The IAM user / role must have permissions for S3 and IAM resources used in
`terraform-aws-etl-pipeline/terraform/main.tf`.)

Optionally create a `production` GitHub Environment so the **Deploy** job can be
gated behind required reviewers:

```bash
gh api -X PUT repos/:owner/:repo/environments/production
```

## 2. Create and push the `main` branch

Currently the default branch is `feature/dockeretl`. Create `main`:

```bash
# from your local clone
git checkout -b main
git push -u origin main

# make main the default branch on GitHub
gh repo edit --default-branch main
```

## 3. Protect the `main` branch

Branch protection rules cannot live in a workflow YAML — apply them once with
the GitHub CLI (requires `admin` on the repo):

```bash
gh api -X PUT repos/:owner/:repo/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["Secret Scan (gitleaks)","Terraform Init & Plan"]}' \
  -F enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  -f restrictions=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false \
  -F required_linear_history=true
```

This configures `main` so that:

- Direct pushes are blocked — changes must come via pull request.
- At least **1 approving review** is required.
- The `Secret Scan (gitleaks)` and `Terraform Init & Plan` checks must pass.
- Force-pushes and branch deletion are disabled.
- Admins are also subject to the rules.

## 4. Working with feature branches

```bash
git checkout -b feature/<name>
# ...make changes...
git push -u origin feature/<name>
gh pr create --base main --head feature/<name> --title "..." --body "..."
```

What runs when:

| Event                          | secret-scan | plan | apply |
| ------------------------------ | :---------: | :--: | :---: |
| Push to `feature/**`           | Yes         | Yes  | No    |
| PR opened/updated against main | Yes         | Yes  | No    |
| Push to `main` (merge)         | Yes         | Yes  | Yes   |

The `terraform-deploy` job is gated by `if: github.ref == 'refs/heads/main'`,
so deploys only happen after a PR is merged into `main`.

## 5. Adjusting the Terraform working directory

If you add more Terraform stacks under other subprojects, either:

- duplicate the `terraform-plan` / `terraform-deploy` jobs with different
  `working-directory` values, or
- convert the workflow to a matrix over stack directories.
