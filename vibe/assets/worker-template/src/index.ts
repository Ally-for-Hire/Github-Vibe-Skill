import { buildResponseBody } from "./response";

export interface Env {}

export default {
  async fetch(request: Request, _env: Env, _ctx: ExecutionContext): Promise<Response> {
    return Response.json(buildResponseBody(request));
  },
};
