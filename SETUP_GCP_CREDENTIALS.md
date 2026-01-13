# Setting Up GCP Credentials for MoneyMaker

This guide will help you create a GCP service account and download the credentials file needed for Firestore access.

## Prerequisites

- A Google Cloud Platform (GCP) account
- A GCP project with Firestore enabled
- `gcloud` CLI installed (optional, but recommended)

## Step 1: Create a GCP Project (if you don't have one)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click "New Project"
4. Enter a project name (e.g., "moneymaker")
5. Click "Create"

## Step 2: Enable Firestore

1. In the GCP Console, go to **Firestore** (or search for it)
2. Click "Create Database"
3. Choose **Native mode** (not Datastore mode)
4. Select a location (e.g., `us-central1`)
5. Click "Create"

## Step 3: Create a Service Account

### Option A: Using GCP Console (Web UI)

1. Go to **IAM & Admin** > **Service Accounts**
2. Click "Create Service Account"
3. Enter details:
   - **Service account name**: `moneymaker-service`
   - **Service account ID**: (auto-generated)
   - **Description**: "Service account for MoneyMaker trading bot"
4. Click "Create and Continue"
5. Grant roles:
   - **Cloud Datastore User** (for Firestore access)
   - **Firebase Admin** (if using Firebase features)
6. Click "Continue" then "Done"

### Option B: Using gcloud CLI

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Create service account
gcloud iam service-accounts create moneymaker-service \
  --display-name="MoneyMaker Service Account"

# Grant Firestore permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:moneymaker-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

## Step 4: Create and Download Service Account Key

### Option A: Using GCP Console

1. Go to **IAM & Admin** > **Service Accounts**
2. Click on your service account (`moneymaker-service`)
3. Go to the **Keys** tab
4. Click "Add Key" > "Create new key"
5. Choose **JSON** format
6. Click "Create"
7. The JSON file will download automatically
8. **Rename it to `gcp-credentials.json`** and place it in the MoneyMaker project root

### Option B: Using gcloud CLI

```bash
# Create and download the key
gcloud iam service-accounts keys create gcp-credentials.json \
  --iam-account=moneymaker-service@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Move it to the project root (if not already there)
mv gcp-credentials.json /path/to/MoneyMaker/
```

## Step 5: Update Your .env File

Make sure your `.env` file includes:

```env
GCP_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-credentials.json
```

## Step 6: Verify Setup

1. Ensure `gcp-credentials.json` is in the project root (not a directory!)
2. Verify it's a valid JSON file:
   ```bash
   # On Windows PowerShell
   Get-Content gcp-credentials.json | ConvertFrom-Json
   
   # On Linux/Mac
   cat gcp-credentials.json | python -m json.tool
   ```
3. Restart Docker containers:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## Security Notes

⚠️ **IMPORTANT**: 
- Never commit `gcp-credentials.json` to git (it's already in `.gitignore`)
- Keep your service account keys secure
- Rotate keys periodically
- Use least-privilege IAM roles

## Troubleshooting

### Error: "Is a directory"
- Make sure `gcp-credentials.json` is a **file**, not a directory
- Delete any directory with that name and create the file instead

### Error: "Permission denied"
- Verify the service account has the `Cloud Datastore User` role
- Check that Firestore is enabled in your project

### Error: "Project not found"
- Verify `GCP_PROJECT_ID` in your `.env` matches your actual project ID
- Ensure the service account belongs to the correct project

## Need Help?

- [GCP Service Accounts Documentation](https://cloud.google.com/iam/docs/service-accounts)
- [Firestore Setup Guide](https://cloud.google.com/firestore/docs/get-started)
- [gcloud CLI Reference](https://cloud.google.com/sdk/gcloud/reference)
