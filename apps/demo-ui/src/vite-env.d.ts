/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_API_KEY: string;
  readonly VITE_UI_PASSWORD: string;
  readonly VITE_UI_PASSWORD_HASH: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
