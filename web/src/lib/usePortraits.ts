import { useEffect, useState } from "react";
import type { Team } from "./types";

const cache: Record<string, string> = {};

/** Face pictures of the given players, drawn in 3D on this phone the first time they are needed (three.js is
 *  loaded only then), then kept for the visit. Empty until ready; the grid shows the animal emoji meanwhile. */
export function usePortraits(ids: string[], teams: Team[]): Record<string, string> {
  const key = ids.join(",");
  const [shots, setShots] = useState<Record<string, string>>(() => ({ ...cache }));
  useEffect(() => {
    const missing = ids.filter((id) => !cache[id]);
    if (!missing.length) return;
    let alive = true;
    import("../components/PlayerModel")
      .then(({ renderPortraits }) => {
        Object.assign(cache, renderPortraits(missing, teams));
        if (alive) setShots({ ...cache });
      })
      .catch(() => undefined); // no WebGL: the emoji stays
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, teams]);
  return shots;
}
