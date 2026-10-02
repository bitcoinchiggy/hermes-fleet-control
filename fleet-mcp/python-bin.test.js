import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { helperSpawnSpec, resolveHelperPython } from "./python-bin.js";

const HERMES_PYTHON = "/home/hermes/.hermes/hermes-agent/venv/bin/python";

function fileFs(real = null) {
  return {
    statSync() {
      return { isFile: () => true };
    },
    realpathSync(candidate) {
      return real ?? candidate;
    },
  };
}

test("a missing managed interpreter is not PATH python3", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hf-control-"));
  assert.equal(resolveHelperPython(root, {}), null);
  assert.equal(helperSpawnSpec(root, path.join(root, "fleet-delegate"), [], {}), null);
});

test("the managed virtualenv python is the spawn command", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hf-control-"));
  const python = path.join(root, "runtime", "venv", "bin", "python");
  fs.mkdirSync(path.dirname(python), { recursive: true });
  fs.writeFileSync(python, "");
  const script = path.join(root, "fleet-delegate");
  const spec = helperSpawnSpec(root, script, ["operator"], {});
  assert.equal(spec.command, python);
  assert.deepEqual(spec.args, [script, "operator"]);
  assert.equal(spec.shell, false);
  assert.equal(spec.command.includes("python3"), false);
});

test("a relative override is refused", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hf-control-"));
  assert.equal(resolveHelperPython(root, { FLEET_CONTROL_PYTHON: "python3" }), null);
  assert.equal(resolveHelperPython(root, { FLEET_CONTROL_PYTHON: "bin/python" }), null);
});

test("the Hermes agent virtualenv is refused even when the file exists", () => {
  assert.equal(
    resolveHelperPython("/work", { FLEET_CONTROL_PYTHON: HERMES_PYTHON }, fileFs()),
    null,
  );
});

test("a symlink into the Hermes agent virtualenv is refused", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hf-control-"));
  const link = path.join(root, "python");
  fs.writeFileSync(link, "");
  assert.equal(
    resolveHelperPython(root, { FLEET_CONTROL_PYTHON: link }, fileFs(HERMES_PYTHON)),
    null,
  );
});

test("an absolute override is spawned as given, not its realpath", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hf-control-"));
  const link = path.join(root, "python");
  const spec = helperSpawnSpec(
    root,
    path.join(root, "fleet-delegate"),
    [],
    { FLEET_CONTROL_PYTHON: link },
    fileFs("/usr/bin/python3.12"),
  );
  assert.equal(spec.command, link);
  assert.notEqual(spec.command, "/usr/bin/python3.12");
});
