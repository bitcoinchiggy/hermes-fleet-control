/**
 * Hermes Control Fleet MCP server.
 *
 * Tools: worker_status, ensure_worker, delegate_worker.
 * There is no send_message tool. Buzz signing stays in fleet-delegate,
 * which reads the selected profile .env itself. Do not put
 * BUZZ_PRIVATE_KEY or BUZZ_FLEET_MEMBERSHIP_TOKEN in this process.
 */

import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const statusBin = path.join(root, "fleet-status");
const ensureBin = path.join(root, "fleet-ensure");
const delegateBin = path.join(root, "fleet-delegate");

const FORBIDDEN_ENV = [
  "BUZZ_PRIVATE_KEY",
  "BUZZ_FLEET_MEMBERSHIP_TOKEN",
  "LITELLM_MASTER_KEY",
  "PVE_TOKEN_SECRET",
];

function helperEnv() {
  const env = { ...process.env };
  for (const key of FORBIDDEN_ENV) {
    delete env[key];
  }
  return env;
}

function refusedEnvironment() {
  return FORBIDDEN_ENV.some((key) => String(process.env[key] || "").trim());
}

function helperFailure() {
  return JSON.stringify({
    accepted: false,
    error: { code: "helper_failed", message: "fleet helper failed" },
  });
}

function forbiddenFailure() {
  return JSON.stringify({
    accepted: false,
    error: {
      code: "forbidden_environment",
      message: "refusing to run where provisioner-only credentials are present",
    },
  });
}

function runHelper(bin, args, stdinText) {
  if (refusedEnvironment()) {
    return Promise.resolve(forbiddenFailure());
  }
  return new Promise((resolve) => {
    let settled = false;
    const finish = (text) => {
      if (settled) {
        return;
      }
      settled = true;
      resolve(text);
    };
    let child;
    try {
      child = spawn(bin, args, {
        shell: false,
        env: helperEnv(),
        stdio: ["pipe", "pipe", "pipe"],
      });
    } catch {
      finish(helperFailure());
      return;
    }
    const chunks = [];
    let total = 0;
    child.stdout.on("data", (chunk) => {
      total += chunk.length;
      if (total <= 1_000_000) {
        chunks.push(chunk);
      }
    });
    child.stderr.on("data", () => {});
    child.on("error", () => finish(helperFailure()));
    child.on("close", () => {
      const text = Buffer.concat(chunks).toString("utf8").trim();
      finish(text || helperFailure());
    });
    child.stdin.on("error", () => {});
    if (stdinText === undefined) {
      child.stdin.end();
    } else {
      child.stdin.end(stdinText);
    }
  });
}

function textResult(text) {
  return { content: [{ type: "text", text }] };
}

const server = new McpServer({
  name: "hermes-fleet-control",
  version: "1.0.0",
});

server.registerTool(
  "worker_status",
  {
    description:
      "Read Fleet worker status. Omit name to list workers. Name selects one public worker document.",
    inputSchema: {
      name: z.string().optional(),
    },
  },
  async ({ name }) => {
    const args = name === undefined ? [] : [name];
    return textResult(await runHelper(statusBin, args));
  },
);

server.registerTool(
  "ensure_worker",
  {
    description:
      "Ensure one Fleet worker by name. The helper sends an empty JSON object and no other fields.",
    inputSchema: {
      name: z.string(),
    },
  },
  async ({ name }) => textResult(await runHelper(ensureBin, [name])),
);

server.registerTool(
  "delegate_worker",
  {
    description:
      "Delegate a task to one ready Fleet worker over Buzz. Signs on Control. Returns relay_accepted when the relay accepts the DM. relay_accepted is not worker execution and not task completion. The worker reply arrives later as a separate Buzz turn. If a delegation call returns an error containing delegation_id, any retry of that same task MUST reuse that exact delegation_id. A caller must not create a new delegation merely because delivery outcome was uncertain. Reusing an id whose delivery is uncertain does not send the message again.",
    inputSchema: {
      worker: z.string(),
      task: z.string().min(1).max(8000),
      delegation_id: z
        .string()
        .regex(/^dlg_[0-9a-f]{32}$/)
        .optional(),
    },
  },
  async ({ worker, task, delegation_id }) => {
    const payload = { worker, task };
    if (delegation_id !== undefined) {
      payload.delegation_id = delegation_id;
    }
    return textResult(await runHelper(delegateBin, [], JSON.stringify(payload)));
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
