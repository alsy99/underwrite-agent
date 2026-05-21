const SESSION_KEY = "underwrite-agent-auth";

const passwordHash = import.meta.env.VITE_UI_PASSWORD_HASH?.trim() || "";
const passwordPlain = import.meta.env.VITE_UI_PASSWORD?.trim() || "";

export function isAuthRequired(): boolean {
  return Boolean(passwordHash || passwordPlain);
}

export function isAuthenticated(): boolean {
  if (!isAuthRequired()) return true;
  return sessionStorage.getItem(SESSION_KEY) === "1";
}

export function clearAuth(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

async function sha256Hex(value: string): Promise<string> {
  const data = new TextEncoder().encode(value);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function verifyPassword(password: string): Promise<boolean> {
  if (passwordHash) {
    return (await sha256Hex(password)) === passwordHash;
  }
  if (passwordPlain) {
    return password === passwordPlain;
  }
  return true;
}

export async function login(password: string): Promise<boolean> {
  const ok = await verifyPassword(password);
  if (ok) sessionStorage.setItem(SESSION_KEY, "1");
  return ok;
}
