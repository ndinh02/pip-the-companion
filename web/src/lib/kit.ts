import { KEEPER_KIT } from "./animals";
import type { Team } from "./types";

/** The kit a player wears: keepers have their own colours, everyone else the team's. */
export function kitOf(playerId: string, teams: Team[]): { primary: string; secondary: string } {
  const teamId = playerId.split("-")[0];
  if (playerId.endsWith("-1")) return KEEPER_KIT[teamId] ?? { primary: "#888888", secondary: "#ffffff" };
  return teams.find((t) => t.team_id === teamId)?.kit ?? { primary: "#888888", secondary: "#ffffff" };
}
