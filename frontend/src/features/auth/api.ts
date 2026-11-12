import { api } from "../../shared/api/client";

export interface User {
  id: number;
  email: string;
  role: string;
  tenant_id: number;
  full_name?: string | null;
  subscription?: { status: string; days_left: number | null; trial_ends_at: string | null; locked: boolean };
}

export interface SignupPayload {
  owner_name: string;
  restaurant_name: string;
  email: string;
  mobile: string;
  password: string;
  address_line: string;
  city: string;
  state_code: string;
  pincode: string;
  gstin?: string;
  billing_cycle: "monthly" | "yearly";
}

export const authApi = {
  signup: (payload: SignupPayload) =>
    api<{ user: Pick<User, "id" | "email" | "role">; trial_ends_at: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  me: () => api<User>("/auth/me"),
  login: (email: string, password: string) =>
    api<{ user: Pick<User, "id" | "email" | "role"> }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  forgotPassword: (email: string) =>
    api<{ message: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, password: string) =>
    api<{ message: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) }),
  logout: () => api<void>("/auth/logout", { method: "POST" }),
};
