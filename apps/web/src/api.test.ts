import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, apiWithWakeRetry, formatMoney, formatPercent } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("cold-start retry", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the payload once a waking service starts answering", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValue(
        new Response(JSON.stringify({ evidence_records: 1272 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const onAttempt = vi.fn();

    const pending = apiWithWakeRetry<{ evidence_records: number }>(
      "/overview",
      onAttempt,
    );
    await vi.runAllTimersAsync();

    expect(await pending).toEqual({ evidence_records: 1272 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(onAttempt).toHaveBeenCalledWith(1, 5);
  });

  it("gives up with the last error rather than retrying forever", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    const pending = apiWithWakeRetry("/overview", undefined, 3);
    const assertion = expect(pending).rejects.toThrow("Failed to fetch");
    await vi.runAllTimersAsync();
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});

describe("finance formatters", () => {
  it("formats integer paise as Indian rupees", () => {
    expect(formatMoney(12_345)).toContain("123.45");
  });

  it("formats decimal ratios as percentages", () => {
    expect(formatPercent(0.875)).toContain("87.5");
  });

  it("lets the browser set multipart boundaries for FormData", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const form = new FormData();
    form.append("file", "csv-data");

    await api<{ ok: boolean }>("/ingestion/preview", {
      method: "POST",
      body: form,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/ingestion/preview",
      expect.objectContaining({ body: form, headers: undefined }),
    );
  });

  it("surfaces row validation details from structured API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              message: "no records were committed",
              errors: ["row 3: invalid amount"],
            },
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(api("/ingestion/commit")).rejects.toThrow(
      "no records were committed: row 3: invalid amount",
    );
  });
});
