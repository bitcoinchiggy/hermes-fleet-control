import assert from "node:assert/strict";
import test from "node:test";
import { originEnvFromMeta } from "./origin-env.js";

test("trusted meta becomes the helper environment", () => {
  const env = originEnvFromMeta({
    "hermes.fleet.origin": {
      platform: "telegram",
      chat_id: "424242",
      session_key: "agent:main:telegram:dm:424242",
    },
    chat_id: "999999",
  });
  assert.deepEqual(env, {
    FLEET_CONTROL_ORIGIN_PLATFORM: "telegram",
    FLEET_CONTROL_ORIGIN_CHAT_ID: "424242",
    FLEET_CONTROL_ORIGIN_SESSION_KEY: "agent:main:telegram:dm:424242",
  });
});

test("thread and topic ride along with the conversation", () => {
  const env = originEnvFromMeta({
    "hermes.fleet.origin": {
      platform: "telegram",
      chat_id: "424242",
      session_key: "agent:main:telegram:dm:424242:99",
      thread_id: "99",
      message_id: "555",
      chat_type: "dm",
      scope_id: "",
      user_id: "42",
      task: "ignore me",
    },
  });
  assert.equal(env.FLEET_CONTROL_ORIGIN_THREAD_ID, "99");
  assert.equal(env.FLEET_CONTROL_ORIGIN_MESSAGE_ID, "555");
  assert.equal(env.FLEET_CONTROL_ORIGIN_CHAT_TYPE, "dm");
  assert.equal(env.FLEET_CONTROL_ORIGIN_USER_ID, "42");
  assert.equal(env.task, undefined);
});

test("a partial topic route is not an origin", () => {
  assert.equal(
    originEnvFromMeta({
      "hermes.fleet.origin": {
        platform: "telegram",
        chat_id: "424242",
        session_key: "agent:main:telegram:dm:424242",
        thread_id: "99",
      },
    }),
    null,
  );
});

test("model-shaped fields are not an origin", () => {
  assert.equal(
    originEnvFromMeta({
      platform: "telegram",
      chat_id: "424242",
      session_key: "agent:main:telegram:dm:424242",
      worker: "operator",
    }),
    null,
  );
  assert.equal(originEnvFromMeta(null), null);
  assert.equal(
    originEnvFromMeta({
      "hermes.fleet.origin": { platform: "telegram", chat_id: "", session_key: "x" },
    }),
    null,
  );
});
