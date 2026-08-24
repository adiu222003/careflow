/**
 * Authentication utilities — token and user storage.
 * Uses localStorage for the token (appropriate for this demo scope).
 * In production, consider httpOnly cookies.
 */
import { User, AuthResponse } from "@/types";
import apiClient from "./api";

const TOKEN_KEY = "careflow_token";
const USER_KEY = "careflow_user";

export function saveAuth(auth: AuthResponse): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, auth.token.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export async function fetchCurrentUser(): Promise<User | null> {
  try {
    const response = await apiClient.get<{ success: true; data: User }>("/auth/me");
    return response.data.data;
  } catch {
    clearAuth();
    return null;
  }
}

export function getRoleHomePath(role: string): string {
  switch (role) {
    case "ADMIN":
      return "/admin/dashboard";
    case "DOCTOR":
      return "/doctor/dashboard";
    case "PATIENT":
    default:
      return "/patient/dashboard";
  }
}
