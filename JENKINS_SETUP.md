# Jenkins Setup Guide – Faceless Video Bot

## Prerequisites

| Requirement | Notes |
|---|---|
| Jenkins 2.387+ | LTS recommended |
| Jenkins agent OS | Ubuntu/Debian (the Jenkinsfile uses `apt-get`) |
| Python 3.11+ | Pre-installed on the agent, OR use a Docker agent |
| FFmpeg | Pre-installed on the agent (the pipeline auto-installs it if missing) |
| Git | Pre-installed; agent must be able to `git push` to your repo |

---

## Step 1 – Required Jenkins Plugins

Install these from **Manage Jenkins → Plugins → Available**:

- **Pipeline** (standard, usually pre-installed)
- **Credentials Binding Plugin** (`withCredentials`)
- **SSH Agent Plugin** (`sshagent`) – for pushing `used_topics.json`
- **Git Plugin** – for `checkout scm`

---

## Step 2 – Add Credentials

Go to **Manage Jenkins → Credentials → (global) → Add Credentials**.

Create one **Secret Text** credential for each of the following:

| Credential ID | Where to get the value |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio |
| `PEXELS_API_KEY` | pexels.com/api |
| `JAMENDO_CLIENT_ID` | developer.jamendo.com |
| `YOUTUBE_CLIENT_SECRETS_JSON` | Paste the **full JSON** from `client_secrets.json` |
| `YOUTUBE_TOKEN_JSON` | Paste the **full JSON** from `token.json` (run locally first) |
| `GROQ_API_KEY` | console.groq.com |
| `YOUTUBE_PRIVACY` | One of: `public`, `unlisted`, `private` |

### Optional credentials

| Credential ID | Notes |
|---|---|
| `VOICE_SAMPLE_B64` | Base64-encoded WAV (only needed if using Coqui voice cloning) |
| `git-ssh-credentials` | SSH private key for pushing to GitHub (see Step 3) |

---

## Step 3 – Git Push Credentials

The pipeline pushes `used_topics.json` back to the repo after each run.

### Option A – SSH Key (recommended)
1. Generate an SSH key pair: `ssh-keygen -t ed25519 -C "jenkins"`
2. Add the **public key** to your GitHub repo as a **Deploy Key** (with write access).
3. Add the **private key** to Jenkins:
   - Kind: **SSH Username with private key**
   - ID: `git-ssh-credentials`

### Option B – HTTPS (GitHub PAT)
Replace the `sshagent` block in the Jenkinsfile with:

```groovy
withCredentials([gitUsernamePassword(credentialsId: 'github-pat', gitToolName: 'Default')]) {
    sh '''
        git config user.name  "jenkins[bot]"
        git config user.email "jenkins[bot]@localhost"
        if [ -f used_topics.json ]; then
            git add used_topics.json
            git diff --cached --quiet || (
                git commit -m "chore: update used_topics.json [skip ci]" &&
                git push origin HEAD
            )
        fi
    '''
}
```

---

## Step 4 – Create the Pipeline Job

1. **New Item → Pipeline** → give it a name (e.g. `faceless-video-bot`).
2. Under **Pipeline → Definition** select **Pipeline script from SCM**.
3. Set **SCM** to **Git**, add your repository URL and credentials.
4. Set **Script Path** to `Jenkinsfile`.
5. Click **Save**.

---

## Step 5 – Enable the Schedule

The `triggers { cron(...) }` block in the Jenkinsfile mirrors the 6 GitHub Actions cron jobs:

| UTC Time | Slot |
|---|---|
| 06:00 | News #1 (top breaking story) |
| 08:00 | Topic #1 (morning topic) |
| 11:00 | News #2 (second breaking story) |
| 13:00 | Topic #2 (afternoon topic) |
| 16:00 | News #3 (third breaking story) |
| 19:00 | Topic #3 (evening topic) |

> **Note:** Jenkins cron triggers only activate after the first manual run or after saving the job.
> Trigger once manually to register the schedule.

---

## Step 6 – Optional: Voice Sample

If you want Coqui voice cloning:

1. Base64-encode your WAV file:
   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("my_voice.wav")) | Set-Clipboard
   ```
2. Add it as a Secret Text credential with ID `VOICE_SAMPLE_B64`.
3. Add an environment variable `HAS_VOICE_SAMPLE = true` in the Jenkins job configuration
   (**Pipeline → Environment variables**).

---

## Manual Trigger

Click **Build with Parameters** on the job to override the slot or topic:

| Parameter | Example Value | Effect |
|---|---|---|
| `SLOT` | `news1` | Fetch top breaking news story |
| `SLOT` | `morning` | Select a morning topic |
| `TOPIC` | `Black holes explained` | Use this explicit topic |
| (both blank) | — | Auto-detect from current UTC hour |

---

## Disabling the GitHub Actions Workflow

Once Jenkins is running, disable the old workflow to avoid duplicate uploads:

```bash
# Via GitHub CLI
gh workflow disable daily_video.yml
```

Or go to **GitHub → Actions → Daily Faceless Video Bot → (three dots) → Disable workflow**.
