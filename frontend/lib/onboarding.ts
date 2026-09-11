import { api } from "@/lib/api";
import type { DatasetDetail } from "@/lib/datasets";

export type OnboardingStatus = {
  has_seen_welcome: boolean;
  has_datasets: boolean;
  has_documents: boolean;
  has_conversations: boolean;
  is_new: boolean;
};

export async function getOnboardingStatus(
  token: string
): Promise<OnboardingStatus> {
  return api<OnboardingStatus>("/users/me/onboarding-status", { token });
}

export async function completeOnboarding(token: string): Promise<void> {
  await api("/users/me/onboarding-complete", { method: "POST", token });
}

export async function loadExampleDataset(
  token: string
): Promise<DatasetDetail> {
  return api<DatasetDetail>("/users/me/load-example-dataset", {
    method: "POST",
    token,
  });
}
