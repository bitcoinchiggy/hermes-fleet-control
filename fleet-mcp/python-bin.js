/**
 * Interpreter selection for the Control Fleet helpers.
 *
 * Hermes can change which python3 is first on PATH. This module never
 * resolves python3 from PATH. It returns the managed virtualenv interpreter
 * or an absolute FLEET_CONTROL_PYTHON override. The Hermes agent virtualenv
 * is refused. A missing interpreter is null so the caller returns
 * helper_failed instead of falling back.
 *
 * The returned path is the virtualenv path, not its realpath. Python uses
 * argv[0] to find the virtualenv prefix.
 */

import fs from "node:fs";
import path from "node:path";

export const HERMES_AGENT_VENV = "/home/hermes/.hermes/hermes-agent/venv";
export const PYTHON_OVERRIDE = "FLEET_CONTROL_PYTHON";

function insideHermesAgentVenv(candidate) {
  const normalized = path.resolve(candidate);
  return (
    normalized === HERMES_AGENT_VENV ||
    normalized.startsWith(HERMES_AGENT_VENV + path.sep)
  );
}

function rejectShape(candidate) {
  if (typeof candidate !== "string" || candidate !== candidate.trim()) {
    return true;
  }
  if (candidate.includes("\n") || candidate.includes("\r") || candidate.includes("\0")) {
    return true;
  }
  if (!path.isAbsolute(candidate)) {
    return true;
  }
  return insideHermesAgentVenv(candidate);
}

/**
 * @param {string} root checkout that contains runtime/venv
 * @param {NodeJS.ProcessEnv} env
 * @param {{ statSync: Function, realpathSync: Function }} fsImpl
 * @returns {string | null}
 */
export function resolveHelperPython(root, env = process.env, fsImpl = fs) {
  const override = String(env?.[PYTHON_OVERRIDE] ?? "").trim();
  const candidate = override
    ? override
    : path.join(root, "runtime", "venv", "bin", "python");
  if (rejectShape(candidate)) {
    return null;
  }
  const normalized = path.resolve(candidate);
  if (insideHermesAgentVenv(normalized)) {
    return null;
  }
  try {
    const stat = fsImpl.statSync(normalized);
    if (!stat.isFile()) {
      return null;
    }
    const real = fsImpl.realpathSync(normalized);
    if (insideHermesAgentVenv(real)) {
      return null;
    }
  } catch {
    return null;
  }
  return normalized;
}

/**
 * Spawn spec for one helper. Null when the managed interpreter is unusable.
 * shell is always false. The script is an argument, so its shebang is ignored.
 */
export function helperSpawnSpec(root, script, args, env = process.env, fsImpl = fs) {
  const command = resolveHelperPython(root, env, fsImpl);
  if (!command) {
    return null;
  }
  return {
    command,
    args: [script, ...args],
    shell: false,
  };
}
