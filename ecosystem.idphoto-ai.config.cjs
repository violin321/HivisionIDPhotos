module.exports = {
  apps: [
    {
      name: 'idphoto-ai-api',
      cwd: '/root/.openclaw/workspace-programmer/HivisionIDPhotos',
      script: '/root/.openclaw/workspace-programmer/HivisionIDPhotos/.venv/bin/uvicorn',
      args: 'deploy_api:app --host 127.0.0.1 --port 18084',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        IDPHOTO_DOWNLOAD_SIGNING_SECRET: process.env.IDPHOTO_DOWNLOAD_SIGNING_SECRET || '',
        IDPHOTO_APP_USERNAME: process.env.IDPHOTO_APP_USERNAME || '',
        IDPHOTO_APP_PASSWORD: process.env.IDPHOTO_APP_PASSWORD || '',
        IDPHOTO_APP_SESSION_SECRET: process.env.IDPHOTO_APP_SESSION_SECRET || ''
      }
    },
    {
      name: 'idphoto-ai-web',
      cwd: '/root/.openclaw/workspace-programmer/HivisionIDPhotos/web',
      script: 'npm',
      args: 'run start -- --hostname 127.0.0.1 --port 18083',
      env: {
        NODE_ENV: 'production',
        NEXT_PUBLIC_API_BASE_URL: '/api'
      }
    }
  ]
}
