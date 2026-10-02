/**
 * Per-call human origin from Hermes MCP `_meta`.
 * The model tool arguments are not consulted.
 */

export const ORIGIN_ENV_KEYS = [
  "FLEET_CONTROL_ORIGIN_PLATFORM",
  "FLEET_CONTROL_ORIGIN_CHAT_ID",
  "FLEET_CONTROL_ORIGIN_SESSION_KEY",
  "FLEET_CONTROL_ORIGIN_THREAD_ID",
  "FLEET_CONTROL_ORIGIN_MESSAGE_ID",
  "FLEET_CONTROL_ORIGIN_CHAT_TYPE",
  "FLEET_CONTROL_ORIGIN_SCOPE_ID",
  "FLEET_CONTROL_ORIGIN_USER_ID",
];

const ROUTE_FIELDS = [
  ["thread_id", "FLEET_CONTROL_ORIGIN_THREAD_ID"],
  ["message_id", "FLEET_CONTROL_ORIGIN_MESSAGE_ID"],
  ["chat_type", "FLEET_CONTROL_ORIGIN_CHAT_TYPE"],
  ["scope_id", "FLEET_CONTROL_ORIGIN_SCOPE_ID"],
  ["user_id", "FLEET_CONTROL_ORIGIN_USER_ID"],
];

const CHAT_TYPES = new Set(["dm", "group", "channel", "thread"]);

export function originEnvFromMeta(meta) {
  if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
    return null;
  }
  const origin = meta["hermes.fleet.origin"];
  if (!origin || typeof origin !== "object" || Array.isArray(origin)) {
    return null;
  }
  const platform = origin.platform;
  const chatId = origin.chat_id;
  const sessionKey = origin.session_key;
  if (
    typeof platform !== "string" ||
    typeof chatId !== "string" ||
    typeof sessionKey !== "string" ||
    !platform ||
    !chatId ||
    !sessionKey
  ) {
    return null;
  }
  const env = {
    FLEET_CONTROL_ORIGIN_PLATFORM: platform,
    FLEET_CONTROL_ORIGIN_CHAT_ID: chatId,
    FLEET_CONTROL_ORIGIN_SESSION_KEY: sessionKey,
  };
  const present = ROUTE_FIELDS.filter(([field]) =>
    Object.prototype.hasOwnProperty.call(origin, field),
  );
  if (present.length === 0) {
    return env;
  }
  if (present.length !== ROUTE_FIELDS.length) {
    return null;
  }
  if (!CHAT_TYPES.has(origin.chat_type)) {
    return null;
  }
  for (const [field, key] of ROUTE_FIELDS) {
    if (typeof origin[field] !== "string") {
      return null;
    }
    env[key] = origin[field];
  }
  return env;
}
