import { describe, expect, it } from "vitest";
import { evidenceFingerprint } from "./reviewEvidence";

describe("review evidence fingerprint", () => {
  it("is deterministic, content-bound, and SHA-256 sized", async () => {
    const first = await evidenceFingerprint({
      question_id: "q_demo",
      amount_paise: 12_345,
    });
    const second = await evidenceFingerprint({
      question_id: "q_demo",
      amount_paise: 12_345,
    });
    const changed = await evidenceFingerprint({
      question_id: "q_demo",
      amount_paise: 12_346,
    });

    expect(first).toMatch(/^[a-f0-9]{64}$/);
    expect(first).toBe(second);
    expect(changed).not.toBe(first);
  });
});
