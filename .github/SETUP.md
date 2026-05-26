# pipeline setup

The workflow in `.github/workflows/pipeline.yml` runs gitleaks, terraform plan,
and (on main only) terraform apply against `terraform-aws-etl-pipeline/terraform`.

## secrets

Add under Settings -> Secrets and variables -> Actions:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

The IAM principal needs S3 + IAM perms for the resources in `main.tf`.

Optionally create a `production` environment so apply needs a manual approval:

```bash
gh api -X PUT repos/:owner/:repo/environments/production
```

## branch protection on main

```bash
gh api -X PUT repos/:owner/:repo/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["secret-scan","plan"]}' \
  -F enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  -f restrictions=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false \
  -F required_linear_history=true
```

Result: no direct pushes, 1 review required, both checks must pass,
no force pushes, no deletions.

## working with feature branches

```bash
git checkout -b feature/<name>
git push -u origin feature/<name>
gh pr create --base main --head feature/<name>
```

| event                     | secret-scan | plan | apply |
| ------------------------- | :---------: | :--: | :---: |
| push to feature/**        | yes         | yes  | no    |
| PR -> main                | yes         | yes  | no    |
| push to main (merge)      | yes         | yes  | yes   |
