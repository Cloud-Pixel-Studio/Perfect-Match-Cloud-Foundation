export type FoundationState = "ready" | "checking" | "unavailable";

export function foundationLabel(state: FoundationState): string {
  const labels: Record<FoundationState, string> = {
    ready: "Operational",
    checking: "Checking",
    unavailable: "Unavailable",
  };
  return labels[state];
}
