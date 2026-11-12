import { api } from "../../shared/api/client";

export interface OnboardingStep { key: string; title: string; route: string; done: boolean; detail: string }
export interface OnboardingStatus { outlet: string; steps: OnboardingStep[]; done: number; total: number; complete: boolean }

export const onboardingApi = {
  status: (outletId: number) => api<OnboardingStatus>(`/outlets/${outletId}/onboarding`),
};
