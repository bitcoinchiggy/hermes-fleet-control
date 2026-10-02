/**
 * Per-call human origin from Hermes MCP `_meta`.
 * The model tool arguments are not consulted.
 */

export const ORIGIN_ENV_KEYS = [
  "FLEET_CONTROL_ORIGIN_PLATFORM",
  "FLEET_CONTROL_ORIGIN_CHAT_ID",
  "FLEET_CONTROL_ORIGIN_SESSION_KEY",
];

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
  return {
    FLEET_CONTROL_ORIGIN_PLATFORM: platform,
    FLEET_CONTROL_ORIGIN_CHAT_ID: chatId,
    FLEET_CONTROL_ORIGIN_SESSION_KEY: sessionKey,
  };
}
