const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export async function api<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: isFormData
      ? options?.headers
      : { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    if (typeof detail === "string") throw new Error(detail);
    if (detail?.message) {
      const rows = Array.isArray(detail.errors) ? detail.errors.join(" · ") : "";
      throw new Error(rows ? `${detail.message}: ${rows}` : detail.message);
    }
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

/**
 * Retry a first page load through a backend cold start.
 *
 * A free-tier container sleeps after inactivity and takes tens of seconds to
 * accept traffic again, so the first visitor of the day would otherwise meet a
 * hard error on a service that is merely waking. Only idempotent reads should
 * use this; it must never wrap an import, a review resolution, or a close.
 */
export async function apiWithWakeRetry<T>(
  path: string,
  onAttempt?: (attempt: number, total: number) => void,
  attempts = 5,
): Promise<T> {
  let lastError: Error = new Error("Request was never attempted");
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await api<T>(path);
    } catch (reason) {
      lastError = reason instanceof Error ? reason : new Error(String(reason));
      if (attempt === attempts) break;
      onAttempt?.(attempt, attempts);
      await new Promise((resolve) => setTimeout(resolve, attempt * 2000));
    }
  }
  throw lastError;
}

export function formatMoney(paise: number, compact = false): string {
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: compact ? 1 : 2,
    notation: compact ? "compact" : "standard",
  }).format(rupees);
}

export function formatPercent(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}
