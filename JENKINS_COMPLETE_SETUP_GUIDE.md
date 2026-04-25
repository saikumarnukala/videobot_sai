# Complete Jenkins Pipeline Setup Guide

## Prerequisites

1. **Jenkins Server** installed and running
2. **Git** installed on Jenkins agent
3. **Python 3.11+** installed on Jenkins agent
4. **FFmpeg** installed on Jenkins agent (or the pipeline will install it)
5. **Required Jenkins Plugins**:
   - Pipeline
   - Credentials Binding Plugin
   - SSH Agent Plugin (for Git push)
   - Git Plugin

## Step 1: Install Required Plugins

1. Go to **Manage Jenkins → Plugins → Available**
2. Search and install:
   - **Pipeline**
   - **Credentials Binding Plugin**
   - **SSH Agent Plugin**
   - **Git Plugin**
3. Restart Jenkins if required

## Step 2: Set Up Credentials in Jenkins

Go to **Manage Jenkins → Credentials → System → Global credentials → Add Credentials**

### Required Credentials (Secret Text type):

| Credential ID | Value to Paste | Source |
|---------------|----------------|--------|
| `PEXELS_API_KEY` | `HrNOgRXtN54HVRPujse8kB6ipnj4P1210VbnfmFTiWrYSFK9AaiYZvl9` | From your `.env` file |
| `JAMENDO_CLIENT_ID` | `86fd69a3` | From your `.env` file |
| `GROQ_API_KEY` | `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` | From your `.env` file |

### YouTube Credentials:

For YouTube upload, you need to create OAuth 2.0 credentials:

1. **Create Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing
   - Enable **YouTube Data API v3**

2. **Create OAuth 2.0 Credentials**:
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Desktop app**
   - Download the JSON file (rename to `client_secrets.json`)

3. **Generate Token**:
   - Run the script locally once to generate `token.json`
   - Or use the YouTube uploader module to authenticate

4. **Add to Jenkins**:
   - Credential ID: `YOUTUBE_CLIENT_SECRETS_JSON`
   - Type: **Secret Text**
   - Value: Paste the **entire content** of `client_secrets.json`
   
   - Credential ID: `YOUTUBE_TOKEN_JSON`
   - Type: **Secret Text**
   - Value: Paste the **entire content** of `token.json`

### Git SSH Credentials (Optional, for pushing used_topics.json):

1. Generate SSH key: `ssh-keygen -t ed25519 -C "jenkins"`
2. Add public key to GitHub as Deploy Key
3. Add private key to Jenkins:
   - Kind: **SSH Username with private key**
   - ID: `git-ssh-credentials`

## Step 3: Create the Jenkins Pipeline Job

1. **New Item → Pipeline** → Name: `faceless-video-bot`
2. Under **Pipeline → Definition**: Select **Pipeline script from SCM**
3. **SCM**: Git
4. **Repository URL**: `https://github.com/your-username/faceless-video-bot.git` (or your repo)
5. **Credentials**: Add Git credentials if repository is private
6. **Branch Specifier**: `*/main`
7. **Script Path**: `Jenkinsfile`
8. Click **Save**

## Step 4: Configure Pipeline Parameters (Optional)

The pipeline already has parameters:
- `SLOT`: Time slot (morning, afternoon, evening, news1, news2, news3)
- `TOPIC`: Specific topic override

You can modify these in the Jenkinsfile if needed.

## Step 5: Test the Pipeline

### Manual Test:
1. Click **Build Now** on the pipeline job
2. Monitor the console output
3. Check for any errors

### Schedule Test:
The pipeline is configured to run 6 times per day:
- 06:00 UTC - News #1
- 08:00 UTC - Morning topic
- 11:00 UTC - News #2
- 13:00 UTC - Afternoon topic
- 16:00 UTC - News #3
- 19:00 UTC - Evening topic

## Step 6: Verify Video Generation

After a successful pipeline run:

1. **Check Console Output** for:
   - "Video published with ID: [VIDEO_ID]"
   - "Pipeline completed successfully"

2. **Check YouTube Channel** for the uploaded video

3. **Check Local Files** (if running locally):
   - `output/final_short.mp4` - Final video
   - `temp/` directory - Temporary files (cleaned up automatically)

## Troubleshooting

### Common Issues:

1. **Authentication Failures**:
   - Verify credentials are correctly set in Jenkins
   - Check credential IDs match the Jenkinsfile

2. **Python/FFmpeg Not Found**:
   - Ensure Python 3.11+ and FFmpeg are installed on Jenkins agent
   - The pipeline will attempt to install FFmpeg if missing

3. **Network Issues**:
   - The pipeline forces IPv4 to prevent network errors
   - Check firewall settings for outbound connections

4. **YouTube Upload Fails**:
   - Verify OAuth credentials are valid
   - Check token hasn't expired (runs for 7 days)
   - Ensure YouTube Data API v3 is enabled

5. **Audio Generation Fails**:
   - Edge TTS requires internet connectivity
   - Check network connectivity from Jenkins agent

## Monitoring and Maintenance

1. **Logs**: Check Jenkins console output for each build
2. **Cleanup**: The pipeline automatically cleans up temporary files
3. **Credential Rotation**: Update credentials in Jenkins when API keys change
4. **Pipeline Updates**: Pull changes from Git to update the Jenkinsfile

## Advanced Configuration

### Environment Variables:
You can modify these in the Jenkinsfile `environment` section:
- `UPLOAD_TO_YOUTUBE`: Set to `'false'` to disable YouTube upload
- `VIDEO_LENGTH_SECONDS`: Video duration (default: 55)
- `RENDER_PRESET`: FFmpeg preset (default: 'medium')
- `EDGE_VOICE`: TTS voice (default: 'ko-KR-HyunsuMultilingualNeural')

### Running on Different Agents:
Modify the `agent any` line to specify a specific agent label if needed.

## Support

For issues with the pipeline, check:
1. Jenkins console output
2. `JENKINS_SETUP.md` in the repository
3. GitHub repository issues

## Next Steps

1. Run a manual build to test the pipeline
2. Verify YouTube upload works
3. Monitor scheduled builds
4. Set up notifications (email, Slack) for build status