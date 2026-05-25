export function buildResponseBody(request: Request) {
  const url = new URL(request.url);

  return {
    ok: true,
    service: "__WORKER_NAME__",
    method: request.method,
    path: url.pathname,
  };
}
