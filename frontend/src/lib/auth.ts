const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type AuthUser = {
  authenticated: boolean;
  user_id?: string;
  email?: string;
  name?: string;
  provider?: string;
};

export async function getMe(): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/api/v1/login/me`, {
    credentials: "include",
  });
  if (!res.ok) return { authenticated: false };
  return res.json();
}

export async function getLoginProviders(): Promise<{
  google: boolean;
  microsoft: boolean;
  demo: boolean;
}> {
  const res = await fetch(`${API_BASE}/api/v1/login/providers`);
  if (!res.ok) return { google: false, microsoft: false, demo: true };
  return res.json();
}

export async function startGoogleLogin(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/login/google`);
  if (!res.ok) throw new Error("Google login not available");
  const data = await res.json();
  return data.auth_url;
}

export async function startMicrosoftLogin(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/login/microsoft`);
  if (!res.ok) throw new Error("Microsoft login not available");
  const data = await res.json();
  return data.auth_url;
}

export async function loginDemo(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/login/demo`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Demo login failed");
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/api/v1/login/logout`, {
    method: "POST",
    credentials: "include",
  });
}
