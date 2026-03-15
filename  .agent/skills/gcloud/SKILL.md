---
name: gcloud-deployment
description: Sud Qo'llanma Botni Google Cloud Run-ga deploy qilish va boshqarish bo'yicha maxsus buyruqlar va yo'riqnomalar (v5 Stable Style).
---

# 🌐 Sud Qo'llanma Bot: GCloud Deployment Skill (v5 Stable)

Ushbu skill botni Google Cloud Run platformasida barqaror holatda saqlash uchun ishlatiladi. Eng xavfsiz yo'li - build va deploy bosqichlarini ajratishdir.

## 🚀 1. Stable Deploy (Proven Method)

Agar bot `Container import failed` yoki `Token is invalid` (NoneType) xatolarini bersa, ushbu ikki bosqichli usuldan foydalaning:

### Bosqich A: Container Build (Cloud Build)
```powershell
cmd /c "gcloud builds submit --tag europe-west4-docker.pkg.dev/educationapp-4780a/cloud-run-source-deploy/sudqollanmabot:stable"
```

### Bosqich B: Cloud Run Deploy (Image orqali)
```powershell
cmd /c "gcloud run deploy sudqollanmabot ^
  --image europe-west4-docker.pkg.dev/educationapp-4780a/cloud-run-source-deploy/sudqollanmabot:stable ^
  --region europe-west4 ^
  --memory 1Gi ^
  --timeout 600 ^
  --concurrency 80 ^
  --service-account 660835097321-compute@developer.gserviceaccount.com ^
  --set-env-vars BOT_TOKEN=8484081250:AAFPhUCTW4HTY23PEyWwQmJPEUC2NIs3Zwg,GEMINI_API_KEY=AIzaSyADwxg3eKsX3bs-hwH8Ke7rvaYgLr3wrHw,GEMINI_MODEL=gemini-2.5-flash,WEBHOOK_URL=https://sudqollanmabot-660835097321.europe-west4.run.app,FIREBASE_CREDENTIALS=serviceAccountKey.json"
```

> [!IMPORTANT]
> - **Memory**: Kamida **1Gi** bo'lishi shart (Firebase va AI modullari ishga tushishi uchun).
> - **Timeout**: **600** soniya (Startup uchun etarli vaqt).
> - **Syntax**: Windows terminalida `^` belgisi yangi qatorga o'tish uchun ishlatiladi.

## 🔐 2. IAM va Ruxsatnomalar (Import Fix)

Agar `Container import failed` xatosi chiqsa, quyidagi ruxsatlarni tekshiring:

```powershell
# Artifact Registry ruxsatini berish
cmd /c "gcloud projects add-iam-policy-binding educationapp-4780a --member=serviceAccount:660835097321-compute@developer.gserviceaccount.com --role=roles/artifactregistry.reader --condition=None"
cmd /c "gcloud projects add-iam-policy-binding educationapp-4780a --member=serviceAccount:service-660835097321@serverless-robot-prod.iam.gserviceaccount.com --role=roles/artifactregistry.reader --condition=None"
```

## 🧠 3. Firestore Index (Vector Search)

Vector search ishlashi uchun zarur index:
```powershell
cmd /c "gcloud alpha firestore indexes composite create --project=educationapp-4780a --collection-group=knowledge_base --query-scope=COLLECTION --field-config=field-path=embedding,vector-config='{\"dimension\":\"768\",\"flat\":\"{}\"}'"
```

## 📊 4. Monitoring

Xatolarni ko'rish:
```powershell
cmd /c "gcloud run services logs read sudqollanmabot --region europe-west4 --limit 20"
```
