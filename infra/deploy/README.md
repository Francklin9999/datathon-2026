# Automatic site deployment

Pushes to `main` run [Deploy site](https://github.com/Francklin9999/datathon-2026/actions/workflows/deploy-site.yml):

1. Install locked dependencies and run the complete deterministic checks.
2. Build the Next.js static export with the existing live API URL and fixtures disabled.
3. Store the export as a GitHub artifact, including commit SHA and file hashes.
4. Use GitHub OIDC to assume `AplombGitHubSiteDeploy`, publish to the existing private web bucket, invalidate CloudFront and wait for completion.
5. Check the deployed revision, every exported page, all compiled static assets, a genuine 404 and API health. Save the object version IDs and results as a deployment artifact.

Pull requests run the same checks and build without AWS credentials or publication. Actions are pinned to commit SHAs. A manual **Run workflow** on `main` republishes the current commit. Deployments are serialized and an in-flight upload is never cancelled by a newer push.

The target is [the existing CloudFront site](https://d1r325uzu5fe7x.cloudfront.net). Public resource identifiers and the live API base are in `site.json`; no GitHub secrets or repository variables are needed. This workflow deploys the frontend. Backend Lambda releases, snapshots, model/Guardrail settings and application infrastructure keep their existing deployment process.

## AWS bootstrap

`github-oidc.template.json` owns the separate `AplombSiteDelivery` CloudFormation stack in `us-east-1`. It creates the GitHub OIDC provider and a role trusting only `repo:Francklin9999/datathon-2026:ref:refs/heads/main`, with audience `sts.amazonaws.com`. The role permits `s3:PutObject` on the exact web bucket's objects and CloudFront create/get invalidation on the exact distribution. It cannot read data, delete objects, alter IAM or deploy stacks. No access keys are stored in GitHub. The stack was created using the official AWS MCP; the application stack was not changed.

For another account, update `site.json` and the bootstrap template together after verifying the target resources. If the account already has a GitHub OIDC provider, reference that provider rather than trying to create a duplicate. Use the [AWS OIDC trust guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html) and the [credentials action](https://github.com/aws-actions/configure-aws-credentials).

## Failure and rollback

Failed checks/builds never enter the publish job. Uploads publish immutable chunks first, navigation payloads next, HTML last and the revision marker last. Changed documents revalidate; immutable chunk URLs cache for a year. Existing objects are not deleted, so old clients can still load their chunks. Removed page objects also remain until an operator explicitly retires them. This is an ordered in-place publication, not an atomic traffic switch; a failed upload can leave a partial update. A failed smoke test reports failure and retains the upload report; it does not claim a healthy release or automatically roll back.

To roll back source, revert the offending commit on `main` and push; the normal pipeline rebuilds and publishes it. GitHub retains site artifacts for 14 days and deployment reports for 30 days. The existing versioned bucket also retains prior object versions; reports identify the uploaded versions for operator recovery. Restoring selected object versions or removing obsolete routes remains operator work outside this upload-only role. CloudFront invalidation is necessary for mutable page URLs ([AWS guidance](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html)).

The smoke test is read-only and does not create sessions or invoke paid model runs. Workflow success verifies static delivery and existing API health, not the correctness of every application interaction.
