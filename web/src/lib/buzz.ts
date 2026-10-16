/** Phone alerts when Pip asks: vibration (Android), a short chime (any phone not on silent) and keeping the screen
 *  awake so the phone is still on when the question comes. All of it is opt-in from one tap, which browsers
 *  require anyway before a page may vibrate or play sound. The choice stays on this device. */

const KEY = "pip.alerts";
let audio: AudioContext | null = null;
let lock: { release: () => Promise<void> } | null = null;

export function alertsWanted(): boolean {
  try {
    return localStorage.getItem(KEY) === "on";
  } catch {
    return false;
  }
}

/** Call from a tap: turns alerts on, unlocks sound and gives a test buzz so the viewer feels it works. */
export async function enableAlerts(): Promise<void> {
  try {
    localStorage.setItem(KEY, "on");
  } catch {
    /* private mode: works for this visit only */
  }
  const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (Ctx && !audio) audio = new Ctx();
  await audio?.resume().catch(() => undefined);
  buzz("ask");
  await keepAwake();
}

export function disableAlerts(): void {
  try {
    localStorage.setItem(KEY, "off");
  } catch {
    /* ignore */
  }
  lock?.release().catch(() => undefined);
  lock = null;
}

/** Ask the browser to keep the screen on (released automatically when the tab is hidden; call again on return). */
export async function keepAwake(): Promise<void> {
  const wl = (navigator as Navigator & { wakeLock?: { request: (t: "screen") => Promise<{ release: () => Promise<void> }> } }).wakeLock;
  if (!wl || document.visibilityState !== "visible") return;
  try {
    lock = await wl.request("screen");
  } catch {
    /* refused (battery saver): alerts still work while the screen is on */
  }
}

/** "ask": two rising notes and a double buzz. "reveal": one soft note and a short buzz. */
export function buzz(kind: "ask" | "reveal"): void {
  if (!alertsWanted()) return;
  navigator.vibrate?.(kind === "ask" ? [90, 70, 90] : 40);
  if (!audio || audio.state !== "running") return;
  const notes = kind === "ask" ? [660, 880] : [520];
  notes.forEach((f, i) => {
    const t = audio!.currentTime + i * 0.13;
    const o = audio!.createOscillator();
    const g = audio!.createGain();
    o.type = "sine";
    o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.18, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
    o.connect(g).connect(audio!.destination);
    o.start(t);
    o.stop(t + 0.25);
  });
}

/** Browsers lock sound again on every page load: call this from the viewer's next tap. */
export async function resumeSound(): Promise<void> {
  if (!alertsWanted()) return;
  const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (Ctx && !audio) audio = new Ctx();
  await audio?.resume().catch(() => undefined);
}
