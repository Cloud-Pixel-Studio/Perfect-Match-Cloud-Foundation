export type IdentityViewState =
  | "loading"
  | "anonymous"
  | "authenticated"
  | "expired"
  | "denied"
  | "error";

export function unauthenticatedState(status: number, hasCsrfCookie: boolean): IdentityViewState {
  if (status === 401) return hasCsrfCookie ? "expired" : "anonymous";
  if (status === 403) return "denied";
  return "error";
}
