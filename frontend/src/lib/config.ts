/**
 * Frontend runtime configuration.
 *
 * Vite only exposes environment variables prefixed with VITE_ to client
 * code, and only at build time - so this is the single place the rest of
 * the app reads configuration from, matching the backend's approach of
 * centralizing settings behind one module.
 */
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
} as const;
