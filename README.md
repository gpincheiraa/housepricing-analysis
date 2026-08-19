# housepricing-analysis

Cloud Run Job for collecting and analyzing Chilean property data.

## Architecture

GitHub Actions -> Artifact Registry -> Cloud Run Job -> Google Cloud APIs

The repository is intentionally small. Mercado Libre OAuth/API integration and
data persistence will be added in later steps.

## GitHub repository variables

Configure these repository variables in GitHub:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REPOSITORY`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOYER_SERVICE_ACCOUNT`
- `GCP_RUNTIME_SERVICE_ACCOUNT`
- `GCS_BUCKET`

Do not put JSON service-account keys or Mercado Libre credentials in GitHub.

## GitHub

Create the repository and push:

```bash
git init
git add .
git commit -m "Initial Cloud Run Job"
git branch -M main
git remote add origin git@github.com:gpincheiraa/housepricing-analysis.git
git push -u origin main
```

