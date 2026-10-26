/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public base URL of the Module 2 FastAPI service. Required. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
