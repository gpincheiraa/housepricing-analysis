# House Pricing Analysis — Comandos GCP

## 1. Seleccionar proyecto

```bash
gcloud config get-value project

gcloud projects list

gcloud config set project TU_PROJECT_ID
```

## 2. Variables

```bash
export PROJECT_ID="$(gcloud config get-value project)"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

export REGION="southamerica-west1"

export DEPLOYER_SA="housepricing-deployer"
export RUNTIME_SA="housepricing-runtime"

export WIF_POOL="github"
export WIF_PROVIDER="github"

export AR_REPOSITORY="housepricing"

echo "PROJECT_ID=$PROJECT_ID"
echo "PROJECT_NUMBER=$PROJECT_NUMBER"
echo "REGION=$REGION"
```

## 3. APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  storage.googleapis.com
```

## 4. Artifact Registry

```bash
gcloud artifacts repositories create "$AR_REPOSITORY" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --repository-format=docker \
  --description="Container images for housepricing-analysis"
```

```bash
gcloud artifacts repositories list \
  --project="$PROJECT_ID" \
  --location="$REGION"
```

## 5. Service Account — Deployer

```bash
gcloud iam service-accounts create "$DEPLOYER_SA" \
  --project="$PROJECT_ID" \
  --display-name="House Pricing GitHub Actions Deployer"

export DEPLOYER_EMAIL="${DEPLOYER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "$DEPLOYER_EMAIL"
```

## 6. Service Account — Runtime

```bash
gcloud iam service-accounts create "$RUNTIME_SA" \
  --project="$PROJECT_ID" \
  --display-name="House Pricing Cloud Run Runtime"

export RUNTIME_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "$RUNTIME_EMAIL"
```

## 7. Permisos Deployer — Cloud Run

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" \
  --role="roles/run.developer"
```

## 8. Permisos Deployer — Artifact Registry

```bash
gcloud artifacts repositories add-iam-policy-binding "$AR_REPOSITORY" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" \
  --role="roles/artifactregistry.writer"
```

## 9. Permisos Deployer — Runtime Service Account

```bash
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_EMAIL" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
```

## 10. Workload Identity Pool

```bash
gcloud iam workload-identity-pools create "$WIF_POOL" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions"
```

## 11. Workload Identity Provider — GitHub OIDC

```bash
gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$WIF_POOL" \
  --display-name="GitHub Actions OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com/" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository == 'gpincheiraa/housepricing-analysis'"
```

## 12. Permitir GitHub → Deployer SA

```bash
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/gpincheiraa/housepricing-analysis"
```

## 13. Obtener Provider completo

```bash
export WIF_PROVIDER_FULL="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"

echo "$WIF_PROVIDER_FULL"
```

## 14. Crear Bucket

```bash
export BUCKET_NAME="${PROJECT_ID}-properties"

gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --uniform-bucket-level-access
```

## 15. Permisos Runtime → Bucket

```bash
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${RUNTIME_EMAIL}" \
  --role="roles/storage.objectUser"
```

## 16. Información completa del Bucket

```bash
gcloud storage buckets describe "gs://${BUCKET_NAME}" \
  --format="yaml"
```

## 17. IAM del Bucket

```bash
gcloud storage buckets get-iam-policy "gs://${BUCKET_NAME}" \
  --format="yaml"
```

## 18. Verificar Uniform Bucket-Level Access

```bash
gcloud storage buckets describe "gs://${BUCKET_NAME}" \
  --format="value(iamConfiguration.uniformBucketLevelAccess.enabled)"
```

## 19. Verificar Service Accounts

```bash
gcloud iam service-accounts list \
  --project="$PROJECT_ID"
```

## 20. Verificar Workload Identity Pool

```bash
gcloud iam workload-identity-pools describe "$WIF_POOL" \
  --project="$PROJECT_ID" \
  --location="global"
```

## 21. Verificar Workload Identity Provider

```bash
gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$WIF_POOL"
```

## 22. Verificar Artifact Registry

```bash
gcloud artifacts repositories describe "$AR_REPOSITORY" \
  --project="$PROJECT_ID" \
  --location="$REGION"
```

## 23. Resumen de variables para GitHub

```bash
echo
echo "===== GITHUB ACTIONS VARIABLES ====="
echo
echo "GCP_PROJECT_ID=$PROJECT_ID"
echo "GCP_REGION=$REGION"
echo "GCP_ARTIFACT_REPOSITORY=$AR_REPOSITORY"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=$WIF_PROVIDER_FULL"
echo "GCP_DEPLOYER_SERVICE_ACCOUNT=$DEPLOYER_EMAIL"
echo "GCP_RUNTIME_SERVICE_ACCOUNT=$RUNTIME_EMAIL"
echo "GCS_BUCKET=$BUCKET_NAME"
echo
```

## 24. Variables de GitHub Actions

Crear estas Repository Variables:

```text
GCP_PROJECT_ID
GCP_REGION
GCP_ARTIFACT_REPOSITORY
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_DEPLOYER_SERVICE_ACCOUNT
GCP_RUNTIME_SERVICE_ACCOUNT
GCS_BUCKET
```

No se necesita una Service Account JSON key.

## 25. Ejecutar Cloud Run Job

```bash
gcloud run jobs execute housepricing-analysis \
  --region="$REGION"
```

## 26. Verificar Cloud Run Job

```bash
gcloud run jobs describe housepricing-analysis \
  --region="$REGION"
```

## 27. Ver ejecuciones

```bash
gcloud run jobs executions list \
  --job="housepricing-analysis" \
  --region="$REGION"
```