// ============================================================
//  FACELESS VIDEO BOT - Daily Jenkins Pipeline
// ============================================================
//
//  Runs on 6 schedules per day and posts a YouTube Short automatically.
//
//  REQUIRED Jenkins Credentials:
//  PEXELS_API_KEY               - Secret Text
//  JAMENDO_CLIENT_ID            - Secret Text
//  YOUTUBE_CLIENT_SECRETS_JSON  - Secret Text
//  YOUTUBE_TOKEN_JSON           - Secret Text
//  GROQ_API_KEY                 - Secret Text
//
//  TTS ENGINE: Edge TTS ONLY - ko-KR-HyunsuMultilingualNeural
//  IPv4 is forced via create_audio.py to prevent network errors.
// ============================================================

pipeline {
    agent any

    triggers {
        cron('''
            0 6  * * *
            0 8  * * *
            0 11 * * *
            0 13 * * *
            0 16 * * *
            0 19 * * *
        ''')
    }

    parameters {
        choice(
            name: 'SLOT',
            choices: ['', 'morning', 'afternoon', 'evening', 'news1', 'news2', 'news3'],
            description: 'Time slot to run. Leave blank for auto-detection from the current hour.'
        )
        string(
            name: 'TOPIC',
            defaultValue: '',
            description: 'Specific topic override. Leave blank to auto-select from topics.json or news feed.'
        )
    }

    options {
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
        disableConcurrentBuilds()
        timestamps()
    }

    environment {
        UPLOAD_TO_YOUTUBE    = 'true'
        VIDEO_LENGTH_SECONDS = '55'
        RENDER_PRESET        = 'medium'
        GROQ_MODEL_DEFAULT   = 'llama-3.3-70b-versatile'
        EDGE_VOICE           = 'ko-KR-HyunsuMultilingualNeural'
        MAX_RETRIES          = '3'
        VOLUME_BOOST         = '+50%'
        WORKSPACE_DIR        = "${env.WORKSPACE}" // Uses the actual Jenkins job workspace path
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Initialize') {
            steps {
                echo "Running pipeline in workspace: ${env.WORKSPACE_DIR}"
                bat 'dir'
            }
        }

        stage('Python Env Setup') {
            steps {
                dir(env.WORKSPACE_DIR) {
                    script {
                        try {
                            bat '''
                                @echo off
                                if not exist .jenkins_venv (
                                    python -m venv .jenkins_venv
                                )
                                call .jenkins_venv\\Scripts\\activate.bat
                                python -m pip install --upgrade pip --quiet
                                pip install -r requirements.txt --quiet
                            '''
                        } finally {
                            // Ensure any stray ffmpeg processes are killed so Jenkins can cleanup durable-task files
                            bat 'taskkill /F /T /IM ffmpeg.exe || echo no ffmpeg found'
                        }
                    }
                }
            }
        }

        stage('Restore Credentials') {
            steps {
                dir(env.WORKSPACE_DIR) {
                    withCredentials([
                        string(credentialsId: 'YOUTUBE_CLIENT_SECRETS_JSON', variable: 'CLIENT_SECRETS'),
                        string(credentialsId: 'YOUTUBE_TOKEN_JSON',           variable: 'TOKEN_JSON')
                    ]) {
                        // Write files safely without worrying about Windows bat multi-line issues
                        writeFile file: 'client_secrets.json', text: env.CLIENT_SECRETS
                        writeFile file: 'token.json', text: env.TOKEN_JSON
                    }
                }
            }
        }

        stage('Select Topic') {
            steps {
                dir(env.WORKSPACE_DIR) {
                    script {
                        def overrideTopic = params.TOPIC?.trim()
                        def overrideSlot  = params.SLOT?.trim()

                        def useTopic  = ''
                        def useNews   = 'false'
                        def newsIndex = '0'
                        def runNumber = env.BUILD_NUMBER

                        if (overrideTopic) {
                            useTopic  = overrideTopic
                            useNews   = 'false'
                            newsIndex = '0'
                        } else if (overrideSlot == 'news1' || overrideSlot == 'news') {
                            useNews   = 'true'
                            newsIndex = '0'
                        } else if (overrideSlot == 'news2') {
                            useNews   = 'true'
                            newsIndex = '1'
                        } else if (overrideSlot == 'news3') {
                            useNews   = 'true'
                            newsIndex = '2'
                        } else if (overrideSlot) {
                            // Extract just the last line of the output to avoid bat echo pollution
                            def out = bat(
                                script: "@echo off\ncall .jenkins_venv\\Scripts\\activate.bat\npython select_topic.py --slot \"${overrideSlot}\" --run-number ${runNumber} --mark-used",
                                returnStdout: true
                            ).trim()
                            useTopic = out.tokenize('\n').last().trim()
                            useNews   = 'false'
                            newsIndex = '0'
                        } else {
                            // Scheduled run: auto-detect slot from current hour
                            // Use groovy's built-in date to avoid batch date formatting issues
                            def hour = new Date().format('HH', TimeZone.getTimeZone('UTC'))
                            
                            if (hour == '06') {
                                useNews   = 'true'
                                newsIndex = '0'
                            } else if (hour == '11') {
                                useNews   = 'true'
                                newsIndex = '1'
                            } else if (hour == '16') {
                                useNews   = 'true'
                                newsIndex = '2'
                            } else {
                                def out = bat(
                                    script: "@echo off\ncall .jenkins_venv\\Scripts\\activate.bat\npython select_topic.py --run-number ${runNumber} --mark-used",
                                    returnStdout: true
                                ).trim()
                                useTopic = out.tokenize('\n').last().trim()
                                useNews   = 'false'
                                newsIndex = '0'
                            }
                        }

                        env.SELECTED_TOPIC = useTopic
                        env.USE_NEWS       = useNews
                        env.NEWS_INDEX     = newsIndex
                        
                        echo "Topic Selected: ${useTopic}"
                        echo "Use News: ${useNews} (Index: ${newsIndex})"
                    }
                }
            }
        }

        stage('Generate & Upload') {
            steps {
                dir(env.WORKSPACE_DIR) {
                    withCredentials([
                        string(credentialsId: 'PEXELS_API_KEY',    variable: 'PEXELS_API_KEY'),
                        string(credentialsId: 'JAMENDO_CLIENT_ID', variable: 'JAMENDO_CLIENT_ID'),
                        string(credentialsId: 'GROQ_API_KEY',      variable: 'GROQ_API_KEY')
                    ]) {
                        script {
                            def groqModel = env.GROQ_MODEL?.trim() ?: env.GROQ_MODEL_DEFAULT
                            def cmd = ""
                            if (env.USE_NEWS == 'true') {
                                cmd = "@echo off\ncall .jenkins_venv\\Scripts\\activate.bat\npython main.py --news --news-index ${env.NEWS_INDEX}"
                            } else {
                                cmd = "@echo off\ncall .jenkins_venv\\Scripts\\activate.bat\npython main.py --topic \"${env.SELECTED_TOPIC}\""
                            }

                            withEnv([
                                "UPLOAD_TO_YOUTUBE=${env.UPLOAD_TO_YOUTUBE}",
                                "VIDEO_LENGTH_SECONDS=${env.VIDEO_LENGTH_SECONDS}",
                                "RENDER_PRESET=${env.RENDER_PRESET}",
                                "GROQ_MODEL=${groqModel}",
                                "EDGE_VOICE=${env.EDGE_VOICE}",
                                "MAX_RETRIES=${env.MAX_RETRIES}",
                                "VOLUME_BOOST=${env.VOLUME_BOOST}"
                            ]) {
                                try {
                                    bat script: cmd
                                } finally {
                                    // Ensure ffmpeg is killed on abort so Jenkins can remove durable-task temp files
                                    bat 'taskkill /F /T /IM ffmpeg.exe || echo no ffmpeg found'
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            dir(env.WORKSPACE_DIR) {
                bat '''
                    @echo off
                    if exist temp\\temp_audio.mp3 del temp\\temp_audio.mp3
                    if exist temp\\temp_subs.json del temp\\temp_subs.json
                    if exist temp\\bg_music.mp3 del temp\\bg_music.mp3
                    if exist output\\final_short.mp4 del output\\final_short.mp4
                    if exist temp\\temp_bg_*.mp4 del temp\\temp_bg_*.mp4
                    if exist token.json del token.json
                    if exist client_secrets.json del client_secrets.json
                '''
            }
        }
        success {
            echo "✅ Pipeline completed successfully. YouTube Short published!"
        }
        failure {
            echo "❌ Pipeline failed. Check console output for details."
        }
    }
}
