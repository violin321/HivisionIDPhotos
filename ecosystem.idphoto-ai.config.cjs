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
        IDPHOTO_APP_SESSION_SECRET: process.env.IDPHOTO_APP_SESSION_SECRET || '',
        AI_PRO_PROVIDER: process.env.AI_PRO_PROVIDER || 'mock',
        GPT_IMAGE_API_BASE: process.env.GPT_IMAGE_API_BASE || '',
        GPT_IMAGE_MODEL: process.env.GPT_IMAGE_MODEL || 'gpt-image-2',
        GPT_IMAGE_API_KEY: process.env.GPT_IMAGE_API_KEY || '',
        AI_PRO_TIMEOUT_SECONDS: process.env.AI_PRO_TIMEOUT_SECONDS || '45'
      }
    },
    {
      name: 'idphoto-ai-web',
      cwd: '/root/.openclaw/workspace-programmer/HivisionIDPhotos/web/.next/standalone',
      script: 'server.js',
      env: {
        NODE_ENV: 'production',
        HOSTNAME: '127.0.0.1',
        PORT: '18083',
        NEXT_PUBLIC_API_BASE_URL: '/api'
      }
    }
  ]
}
