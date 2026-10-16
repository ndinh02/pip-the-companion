/** Each phone gets a random-looking animal for this room, derived from its random device id: the TV can show who
 *  picked what ("🦊 🐼 said Foul") without names, accounts or typing (AGENTS.md rules 5 and 6). Two phones may
 *  share an animal; that is fine for a living-room game. */
const AVATARS = ["🦊", "🐼", "🐨", "🐯", "🐸", "🐵", "🐧", "🦁", "🐮", "🐷", "🐙", "🦉", "🐢", "🦄", "🐳", "🦔"];

export function avatarOf(device: string): string {
  let h = 2166136261;
  for (let i = 0; i < device.length; i++) h = Math.imul(h ^ device.charCodeAt(i), 16777619);
  return AVATARS[(h >>> 0) % AVATARS.length];
}
