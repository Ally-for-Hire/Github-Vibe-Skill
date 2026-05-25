import { describe, expect, it } from "vitest";
import { buildResponseBody } from "../src/response";

describe("buildResponseBody", () => {
  it("returns request metadata", () => {
    const body = buildResponseBody(new Request("https://example.test/health", { method: "POST" }));

    expect(body).toEqual({
      ok: true,
      service: "__WORKER_NAME__",
      method: "POST",
      path: "/health",
    });
  });
});
