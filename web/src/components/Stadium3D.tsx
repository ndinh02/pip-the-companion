import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { Tracking } from "../lib/tracking";
import { animalOf, KEEPER_KIT } from "../lib/animals";
import type { CameraId } from "../lib/cameras";
import { makeCharacter, type Character } from "./characters";
import { newGait, samplePoint, separate, stepGait, type GaitState } from "./locomotion";
import type { Team } from "../lib/types";

/** TV-like 3D view of the synthetic match, driven by the 5 Hz tracking.
 *
 *  Players are simple, club-neutral figures in kit colours with their shirt number above them (no likenesses,
 *  AGENTS.md rule 4). Because the data is synthetic, every player's position is known exactly, so a followed
 *  player keeps their marker in every camera. With a broadcaster's real tracking data the same would hold;
 *  spotting players in real video is a different, much harder problem and is not attempted here. */

export interface Stadium3DProps {
  tracking: Tracking;
  teams: Team[];
  /** Match time to show (ms). Between updates the view runs on smoothly at `speed`. */
  tMs: number;
  speed: number;
  running: boolean;
  camera: CameraId;
  /** What the auto-director should frame. */
  focus: { kind: "play" | "setpiece" | "var" | "replay" | "player"; x?: number; y?: number; playerId?: string | null; defending?: string };
  ringId?: string | null;
  followed?: Record<string, number>;
  /** Show the "REPLAY" badge. */
  replay?: boolean;
  /** Goals: for a while after each, the scoring team celebrates and the other team hangs its heads (poses only). */
  goals?: { t_ms: number; team_id: string; player_id: string }[];
  /** Broadcast-style badge, e.g. "REPLAY" or "VAR CHECK". */
  badge?: string | null;
}

const CELEBRATE_MS = 20_000; // match time players react to a goal
const L = 105;
const W = 68;
// pitch metres (x along, y across, origin bottom-left) -> three.js (x right, y up, z towards the main stand)
const toX = (x: number) => x - L / 2;
const toZ = (y: number) => W / 2 - y;

// ---------- static scenery --------------------------------------------------------------------------------------

function pitchTexture(): THREE.CanvasTexture {
  const s = 10; // px per metre
  const pad = 5;
  const c = document.createElement("canvas");
  c.width = (L + 2 * pad) * s;
  c.height = (W + 2 * pad) * s;
  const g = c.getContext("2d")!;
  for (let i = 0; i < 24; i++) {
    g.fillStyle = i % 2 ? "#2c7a3f" : "#2f8445";
    g.fillRect((i * c.width) / 24, 0, c.width / 24 + 1, c.height);
  }
  g.translate(pad * s, pad * s);
  g.strokeStyle = "rgba(255,255,255,0.92)";
  g.lineWidth = 0.14 * s;
  const rect = (x: number, y: number, w: number, h: number) => g.strokeRect(x * s, y * s, w * s, h * s);
  const arc = (x: number, y: number, r: number, a0: number, a1: number) => {
    g.beginPath();
    g.arc(x * s, y * s, r * s, a0, a1);
    g.stroke();
  };
  rect(0, 0, L, W);
  g.beginPath();
  g.moveTo((L / 2) * s, 0);
  g.lineTo((L / 2) * s, W * s);
  g.stroke();
  arc(L / 2, W / 2, 9.15, 0, Math.PI * 2);
  for (const [x0, dir] of [[0, 1], [L, -1]] as const) {
    const bx = dir > 0 ? 0 : L - 16.5;
    rect(bx, W / 2 - 20.16, 16.5, 40.32);
    rect(dir > 0 ? 0 : L - 5.5, W / 2 - 9.16, 5.5, 18.32);
    const spot = x0 + dir * 11;
    g.fillStyle = "white";
    g.beginPath();
    g.arc(spot * s, (W / 2) * s, 0.25 * s, 0, Math.PI * 2);
    g.fill();
    const a = Math.acos(5.5 / 9.15);
    if (dir > 0) arc(spot, W / 2, 9.15, -a, a);
    else arc(spot, W / 2, 9.15, Math.PI - a, Math.PI + a);
  }
  for (const [cx, cy] of [[0, 0], [L, 0], [0, W], [L, W]]) arc(cx, cy, 1, 0, Math.PI * 2);
  g.fillStyle = "white";
  g.beginPath();
  g.arc((L / 2) * s, (W / 2) * s, 0.25 * s, 0, Math.PI * 2);
  g.fill();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

function addScenery(scene: THREE.Scene) {
  const pad = 5;
  const pitch = new THREE.Mesh(new THREE.PlaneGeometry(L + 2 * pad, W + 2 * pad), new THREE.MeshStandardMaterial({ map: pitchTexture(), roughness: 0.95 }));
  pitch.rotation.x = -Math.PI / 2;
  scene.add(pitch);
  const surround = new THREE.Mesh(new THREE.PlaneGeometry(220, 170), new THREE.MeshStandardMaterial({ color: "#1d4a2b", roughness: 1 }));
  surround.rotation.x = -Math.PI / 2;
  surround.position.y = -0.02;
  scene.add(surround);

  // goals: posts, bar and a light net
  const white = new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: 0.4 });
  const net = new THREE.MeshBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.18, side: THREE.DoubleSide, wireframe: true });
  for (const side of [-1, 1]) {
    const gx = side * (L / 2);
    for (const pz of [-3.66, 3.66]) {
      const post = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.44, 8), white);
      post.position.set(gx, 1.22, pz);
      scene.add(post);
    }
    const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 7.32, 8), white);
    bar.rotation.x = Math.PI / 2;
    bar.position.set(gx, 2.44, 0);
    scene.add(bar);
    const back = new THREE.Mesh(new THREE.PlaneGeometry(7.32, 2.44, 14, 5), net);
    back.rotation.y = Math.PI / 2;
    back.position.set(gx + side * 1.8, 1.22, 0);
    scene.add(back);
  }

  // stands under floodlights: dark tiers with a yellow rim (brand Floodlight)
  const stand = new THREE.MeshStandardMaterial({ color: "#16233a", roughness: 0.9 });
  const rim = new THREE.MeshBasicMaterial({ color: "#FFD23F" });
  const tiers: [number, number, number, number, number][] = [
    // x, z, width, depth, rotationY
    [0, -W / 2 - 14, L + 30, 16, 0],
    [0, W / 2 + 14, L + 30, 16, Math.PI],
    [-L / 2 - 16, 0, W + 10, 16, Math.PI / 2],
    [L / 2 + 16, 0, W + 10, 16, -Math.PI / 2],
  ];
  for (const [x, z, w, d, ry] of tiers) {
    const g = new THREE.Group();
    for (let i = 0; i < 4; i++) {
      const step = new THREE.Mesh(new THREE.BoxGeometry(w, 1.6 + i * 1.8, d / 4), stand);
      step.position.set(0, (1.6 + i * 1.8) / 2, -d / 2 + (i + 0.5) * (d / 4));
      g.add(step);
    }
    const edge = new THREE.Mesh(new THREE.BoxGeometry(w, 0.25, 0.25), rim);
    edge.position.set(0, 1.7, -d / 2);
    g.add(edge);
    g.position.set(x, 0, z);
    g.rotation.y = ry;
    scene.add(g);
  }
  // floodlight towers
  for (const [x, z] of [[-L / 2 - 12, -W / 2 - 12], [L / 2 + 12, -W / 2 - 12], [-L / 2 - 12, W / 2 + 12], [L / 2 + 12, W / 2 + 12]]) {
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.6, 34, 8), stand);
    pole.position.set(x, 17, z);
    scene.add(pole);
    const lamp = new THREE.Mesh(new THREE.BoxGeometry(5, 2.5, 0.6), new THREE.MeshBasicMaterial({ color: "#fff6d6" }));
    lamp.position.set(x, 34, z);
    lamp.lookAt(0, 0, 0);
    scene.add(lamp);
  }

  // dusk sky: deep navy overhead, a warm glow on the horizon
  const skyCanvas = document.createElement("canvas");
  skyCanvas.width = 4;
  skyCanvas.height = 256;
  const sg = skyCanvas.getContext("2d")!;
  const grad = sg.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0, "#070e1c");
  grad.addColorStop(0.55, "#132542");
  grad.addColorStop(0.8, "#4a3a5c");
  grad.addColorStop(1, "#d9825b");
  sg.fillStyle = grad;
  sg.fillRect(0, 0, 4, 256);
  const skyTex = new THREE.CanvasTexture(skyCanvas);
  skyTex.colorSpace = THREE.SRGBColorSpace;
  const sky = new THREE.Mesh(new THREE.SphereGeometry(400, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshBasicMaterial({ map: skyTex, side: THREE.BackSide, fog: false }));
  scene.add(sky);

  // floodlight glow
  const glowCanvas = document.createElement("canvas");
  glowCanvas.width = glowCanvas.height = 64;
  const gg = glowCanvas.getContext("2d")!;
  const rg = gg.createRadialGradient(32, 32, 0, 32, 32, 32);
  rg.addColorStop(0, "rgba(255,248,220,1)");
  rg.addColorStop(0.3, "rgba(255,236,180,0.5)");
  rg.addColorStop(1, "rgba(255,236,180,0)");
  gg.fillStyle = rg;
  gg.fillRect(0, 0, 64, 64);
  const glowTex = new THREE.CanvasTexture(glowCanvas);
  for (const [x, z] of [[-L / 2 - 12, -W / 2 - 12], [L / 2 + 12, -W / 2 - 12], [-L / 2 - 12, W / 2 + 12], [L / 2 + 12, W / 2 + 12]]) {
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
    glow.scale.set(22, 22, 1);
    glow.position.set(x, 34, z);
    scene.add(glow);
  }

  // a crowd on the stands: little round fans in both teams' colours (one instanced mesh, cheap)
  const fanGeo = new THREE.SphereGeometry(0.42, 8, 6);
  const fanMat = new THREE.MeshStandardMaterial({ roughness: 0.9 });
  const fans = new THREE.InstancedMesh(fanGeo, fanMat, 2600);
  const colours = ["#2E7FC4", "#C8692F", "#F6F3EC", "#2E7FC4", "#C8692F", "#3b4a63"].map((c) => new THREE.Color(c));
  const m4 = new THREE.Matrix4();
  let n = 0;
  const rand = (() => {
    let seed = 7;
    return () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  })();
  for (const [x, z, w, d, ry] of tiers) {
    for (let row = 0; row < 4 && n < fans.count; row++) {
      const y = 1.6 + row * 1.8 + 0.35;
      const depth = -d / 2 + (row + 0.5) * (d / 4);
      for (let k = -w / 2 + 1; k < w / 2 - 1 && n < fans.count; k += 1.2) {
        if (rand() < 0.18) continue; // empty seats
        const local = new THREE.Vector3(k + (rand() - 0.5) * 0.4, y, depth);
        local.applyAxisAngle(new THREE.Vector3(0, 1, 0), ry);
        m4.makeTranslation(x + local.x, local.y, z + local.z);
        fans.setMatrixAt(n, m4);
        fans.setColorAt(n, colours[Math.floor(rand() * colours.length)]);
        n++;
      }
    }
  }
  fans.count = n;
  scene.add(fans);

  scene.add(new THREE.HemisphereLight("#e8f0ff", "#1d3b26", 1.1));
  const sun = new THREE.DirectionalLight("#fff4dd", 1.6);
  sun.position.set(-30, 60, 40);
  scene.add(sun);
}

// ---------- players and ball ------------------------------------------------------------------------------------

function numberSprite(text: string, fg: string, bg: string): THREE.Sprite {
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 128;
  const g = c.getContext("2d")!;
  g.fillStyle = bg;
  g.beginPath();
  g.arc(64, 64, 56, 0, Math.PI * 2);
  g.fill();
  g.lineWidth = 8;
  g.strokeStyle = fg;
  g.stroke();
  g.fillStyle = fg;
  g.font = "800 64px 'Be Vietnam Pro', system-ui, sans-serif";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(text, 64, 68);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, sizeAttenuation: false }));
  sprite.scale.set(0.024, 0.024, 1); // fraction of the screen height: same size in every camera
  sprite.renderOrder = 10;
  return sprite;
}

interface Body {
  group: THREE.Group;
  char: Character;
  label: THREE.Sprite;
  ring: THREE.Mesh; // player on the ball
  follow: THREE.Mesh; // followed by phones in the room
  followTag: THREE.Sprite | null;
  followCount: number;
  gait: GaitState;
  offset: [number, number]; // visual separation nudge (metres), eased
  phase: number; // so celebrating players do not jump in step
}

function makeBody(id: string, team: Team | undefined): Body {
  const teamId = id.split("-")[0];
  const isKeeper = id.endsWith("-1");
  const kit = isKeeper ? (KEEPER_KIT[teamId] ?? { primary: "#888888", secondary: "#ffffff" }) : (team?.kit ?? { primary: "#888888", secondary: "#ffffff" });
  const group = new THREE.Group();
  const char = makeCharacter(animalOf(id), kit.primary, kit.secondary);
  char.root.scale.setScalar(1.35); // a touch larger than life so they read in the wide shots
  const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.55, 18), new THREE.MeshBasicMaterial({ color: "#000", transparent: true, opacity: 0.3 }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.02;
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.85, 1.05, 32), new THREE.MeshBasicMaterial({ color: "#F6F3EC", transparent: true, opacity: 0.95 }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.04;
  ring.visible = false;
  const follow = new THREE.Mesh(new THREE.RingGeometry(1.15, 1.45, 40), new THREE.MeshBasicMaterial({ color: "#FFD23F" }));
  follow.rotation.x = -Math.PI / 2;
  follow.position.y = 0.05;
  follow.visible = false;
  const label = numberSprite(id.split("-")[1], kit.secondary, kit.primary);
  label.position.y = 3.3;
  group.add(char.root, shadow, ring, follow, label);
  return { group, char, label, ring, follow, followTag: null, followCount: 0, gait: newGait(), offset: [0, 0], phase: [...id].reduce((h, ch) => h + ch.charCodeAt(0) * 0.7, 0) % Math.PI };
}

/** Ball height is not in the 2D tracking: long, fast flights (crosses, clearances, long passes) get an arc. */
function ballHeights(tr: Tracking): Float32Array {
  const xs = tr.x.ball;
  const ys = tr.y.ball;
  const n = xs.length;
  const z = new Float32Array(n);
  const dt = 1 / tr.hz;
  let i = 1;
  while (i < n) {
    const sp = Math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]) / 10 / dt;
    if (sp < 2) {
      i++;
      continue;
    }
    let j = i;
    let dist = 0;
    while (j < n && Math.hypot(xs[j] - xs[j - 1], ys[j] - ys[j - 1]) / 10 / dt >= 2) {
      dist += Math.hypot(xs[j] - xs[j - 1], ys[j] - ys[j - 1]) / 10;
      j++;
    }
    const secs = (j - i + 1) * dt;
    if (dist > 22 && dist / secs > 12) {
      const h = Math.min(11, 0.13 * dist);
      let run = 0;
      for (let k = i; k < j; k++) {
        run += Math.hypot(xs[k] - xs[k - 1], ys[k] - ys[k - 1]) / 10;
        const s = run / dist;
        z[k] = 4 * h * s * (1 - s);
      }
    }
    i = j + 1;
  }
  return z;
}

/** First and last array index of the period that contains frame `i` (splines must not cross half-time). */
function periodBounds(tr: Tracking, i: number): [number, number] {
  let start = 0;
  for (const p of tr.periods) {
    if (i < start + p.frames) return [start, start + p.frames - 1];
    start += p.frames;
  }
  return [0, start - 1];
}

function frameIndex(tr: Tracking, tMs: number): { i0: number; i1: number; a: number } {
  const step = 1000 / tr.hz;
  let offset = 0;
  let p = tr.periods[0];
  for (const q of tr.periods) if (tMs >= q.start_ms) p = q;
  for (const q of tr.periods) {
    if (q === p) break;
    offset += q.frames;
  }
  const f = Math.max(0, Math.min(p.frames - 1, (tMs - p.start_ms) / step));
  const i0 = Math.floor(f);
  return { i0: offset + i0, i1: offset + Math.min(p.frames - 1, i0 + 1), a: f - i0 };
}

// ---------- the component ---------------------------------------------------------------------------------------

export default function Stadium3D(props: Stadium3DProps) {
  const host = useRef<HTMLDivElement>(null);
  const live = useRef(props);
  live.current = props;
  const propAt = useRef(performance.now());
  const lastT = useRef(props.tMs);
  if (lastT.current !== props.tMs) {
    lastT.current = props.tMs;
    propAt.current = performance.now();
  }

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#0b1626");
    scene.fog = new THREE.Fog("#1a2238", 160, 380);
    addScenery(scene);
    const cam = new THREE.PerspectiveCamera(32, 16 / 9, 0.5, 600);

    const tr = live.current.tracking;
    const z = ballHeights(tr);
    const bodies = new Map<string, Body>();
    for (const id of tr.entities) {
      if (id === "ball") continue;
      const team = live.current.teams.find((t) => id.startsWith(`${t.team_id}-`));
      const b = makeBody(id, team);
      scene.add(b.group);
      bodies.set(id, b);
    }
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.24, 16, 12), new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: 0.35 }));
    const ballShadow = new THREE.Mesh(new THREE.CircleGeometry(0.28, 16), new THREE.MeshBasicMaterial({ color: "#000", transparent: true, opacity: 0.35 }));
    ballShadow.rotation.x = -Math.PI / 2;
    ballShadow.position.y = 0.03;
    scene.add(ball, ballShadow);
    // VAR line: across the pitch at the defending team's second-last player, shown in the overhead camera
    const varLine = new THREE.Mesh(new THREE.PlaneGeometry(0.25, W), new THREE.MeshBasicMaterial({ color: "#6CB4EE", transparent: true, opacity: 0.85 }));
    varLine.rotation.x = -Math.PI / 2;
    varLine.position.y = 0.06;
    varLine.visible = false;
    scene.add(varLine);

    const camPos = new THREE.Vector3(0, 30, 75);
    const camTarget = new THREE.Vector3(0, 0, 0);
    const wantPos = new THREE.Vector3();
    const wantTarget = new THREE.Vector3();
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let lastCamera: string | null = null;

    const resize = () => {
      const w = el.clientWidth || 1;
      const h = el.clientHeight || 1;
      renderer.setSize(w, h, false);
      cam.aspect = w / h;
      cam.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    let raf = 0;
    let lastFrame = performance.now();
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const p = live.current;
      // run smoothly between the 10 updates per second the screen gives us
      const ahead = p.running ? Math.min(150, performance.now() - propAt.current) * p.speed : 0;
      const t = p.tMs + ahead;
      const { i0, i1, a } = frameIndex(tr, t);

      const bx0 = tr.x.ball[i0];
      const bx1 = tr.x.ball[i1];
      const bx = (bx0 + (bx1 - bx0) * a) / 10;
      const by = (tr.y.ball[i0] + (tr.y.ball[i1] - tr.y.ball[i0]) * a) / 10;
      const bz = z[i0] + (z[i1] - z[i0]) * a;
      ball.position.set(toX(bx), 0.24 + bz, toZ(by));
      ballShadow.position.set(toX(bx), 0.03, toZ(by));

      // real time since the last drawn frame, turned into match time (0 while paused)
      const nowReal = performance.now();
      const realDt = Math.min(0.1, (nowReal - lastFrame) / 1000);
      lastFrame = nowReal;
      const matchDt = p.running ? realDt * p.speed : 0;

      // 1. smooth positions (Catmull-Rom through the 5 Hz samples) and velocity over the last 0.1 s of match time
      const { i0: j0, a: ja } = frameIndex(tr, t - 100);
      const per = periodBounds(tr, i0);
      const perPrev = periodBounds(tr, j0);
      const onPitch: { id: string; b: Body; x: number; z: number; vx: number; vz: number }[] = [];
      for (const [id, b] of bodies) {
        const pt = samplePoint(tr.x[id], tr.y[id], i0, a, per[0], per[1]);
        if (pt === null) {
          b.group.visible = false;
          b.gait = newGait();
          continue;
        }
        const [px, py] = pt;
        const [qx, qy] = samplePoint(tr.x[id], tr.y[id], j0, ja, perPrev[0], perPrev[1]) ?? pt;
        let vx = (toX(px) - toX(qx)) / 0.1;
        let vz = (toZ(py) - toZ(qy)) / 0.1;
        if (Math.hypot(vx, vz) > 12) vx = vz = 0; // a jump (coming on, half-time) is not a run
        onPitch.push({ id, b, x: toX(px), z: toZ(py), vx, vz });
      }

      // 2. personal space: nudge overlapping bodies apart (visual only; the data is unchanged)
      const spaced = separate(onPitch.map((l) => [l.x, l.z] as [number, number]));

      let ringPos: THREE.Vector3 | null = null;
      const goal = p.goals?.find((g) => t >= g.t_ms && t < g.t_ms + CELEBRATE_MS);
      for (let k = 0; k < onPitch.length; k++) {
        const { id, b, x, z, vx, vz } = onPitch[k];
        const ease = Math.min(1, realDt * 10);
        b.offset[0] += (spaced[k][0] - x - b.offset[0]) * ease;
        b.offset[1] += (spaced[k][1] - z - b.offset[1]) * ease;
        b.group.visible = true;
        b.group.position.set(x + b.offset[0], 0, z + b.offset[1]);

        // 3. gait, facing and lean from the real speed
        const toBall = Math.atan2(ball.position.x - x, ball.position.z - z);
        const [gait, pose] = stepGait(b.gait, vx, vz, toBall, matchDt);
        b.gait = gait;
        // legs swing along the direction of travel relative to the body: forwards, sideways or backpedalling
        b.char.legs[0].rotation.set(-pose.swingSide, 0, pose.swingFwd);
        b.char.legs[1].rotation.set(pose.swingSide, 0, -pose.swingFwd);
        b.char.arms[0].rotation.z = -pose.swingFwd * 0.8;
        b.char.arms[1].rotation.z = pose.swingFwd * 0.8;
        // goal reactions: arms up and jumping for the scorers, heads down for the others (positions stay the data's)
        const cel = goal ? Math.min(1, (t - goal.t_ms) / 400, (goal.t_ms + CELEBRATE_MS - t) / 3_000) : 0;
        let lift = 0;
        let jump = 0;
        let droop = 0;
        if (cel > 0) {
          if (id.startsWith(`${goal!.team_id}-`)) {
            const scorer = id === goal!.player_id;
            const beat = Math.abs(Math.sin((t / 1000) * Math.PI * (scorer ? 2.4 : 1.9) + b.phase));
            // arms out in a waving "V" (straight up would hide behind the big chibi heads)
            lift = cel * (scorer ? 1.75 + 0.35 * beat : 1.45 + 0.3 * beat);
            jump = cel * beat * (scorer ? 0.6 : 0.35);
          } else droop = cel * 0.15;
        }
        b.char.arms[0].rotation.x = 0.25 + lift;
        b.char.arms[1].rotation.x = -0.25 - lift;
        b.char.body.position.y = pose.hop;
        b.char.root.position.y = jump; // the whole character leaves the ground, legs included
        b.char.root.rotation.z = -pose.lean - droop; // lean into the run (local +x is forward); slump after conceding
        b.group.rotation.y = pose.heading - Math.PI / 2;

        const isRing = p.ringId === id;
        b.ring.visible = isRing;
        if (isRing) ringPos = b.group.position;
        const n = p.followed?.[id] ?? 0;
        b.follow.visible = n > 0;
        if (n !== b.followCount) {
          if (b.followTag) b.group.remove(b.followTag);
          b.followTag = n > 0 ? numberSprite(n > 1 ? `★${n}` : "★", "#0E1A2B", "#FFD23F") : null;
          if (b.followTag) {
            b.followTag.position.y = 4.1;
            b.followTag.scale.set(0.03, 0.03, 1);
            b.group.add(b.followTag);
          }
          b.followCount = n;
        }
      }

      // ---- cameras ----
      const f = p.focus;
      let cid: CameraId = p.camera;
      if (cid === "auto") {
        if (f.kind === "var") cid = "overhead";
        else if (f.kind === "replay" || f.kind === "player") cid = "close";
        else if (f.kind === "setpiece") cid = (f.x ?? bx) > L / 2 ? "goal-right" : "goal-left";
        else cid = "broadcast";
      }
      const fx = toX(bx);
      const fz = toZ(by);
      const followId = Object.entries(p.followed ?? {}).sort((x, y) => y[1] - x[1])[0]?.[0];
      const picked = f.playerId ? bodies.get(f.playerId) : undefined;
      const subject = ((f.kind === "replay" || f.kind === "player") && picked?.group.visible && picked.group.position) || (f.kind === "replay" && ringPos) || (followId && bodies.get(followId)?.group.visible ? bodies.get(followId)!.group.position : null);
      switch (cid) {
        case "broadcast":
          wantTarget.set(fx * 0.85, 0, fz * 0.35);
          wantPos.set(fx * 0.7, 24, W / 2 + 30);
          break;
        case "opposite":
          wantTarget.set(fx * 0.85, 0, fz * 0.35);
          wantPos.set(fx * 0.7, 24, -W / 2 - 30);
          break;
        case "goal-left":
          wantTarget.set(-L / 2 + 11, 0, fz * 0.3);
          wantPos.set(-L / 2 - 6, 17, fz * 0.12);
          break;
        case "goal-right":
          wantTarget.set(L / 2 - 11, 0, fz * 0.3);
          wantPos.set(L / 2 + 6, 17, fz * 0.12);
          break;
        case "close": {
          const c = subject ?? ball.position;
          // stay over the pitch: near the main-stand touchline, film from the pitch side instead of from inside the stand
          const side = c.z > W / 2 - 16 ? -1 : 1;
          wantTarget.set(c.x, 1, c.z);
          wantPos.set(Math.max(-L / 2 - 4, Math.min(L / 2 + 4, c.x * 0.92)), 7, c.z + side * 13);
          break;
        }
        case "overhead": {
          // frame the ball and the goal being attacked, so attacker and last defenders are in view
          const gx = (bx > L / 2 ? 1 : -1) * (L / 2 - 8);
          const cx = (fx + gx) / 2;
          wantTarget.set(cx, 0, fz * 0.4);
          wantPos.set(cx, 62, fz * 0.4 + 8);
          break;
        }
      }
      // VAR line at the defending side's second-last player (overhead camera only)
      varLine.visible = cid === "overhead";
      if (varLine.visible) {
        const end = bx > L / 2 ? 1 : -1;
        const near = [...bodies.entries()]
          .filter(([id, b]) => b.group.visible && (!f.defending || id.startsWith(`${f.defending}-`)))
          .map(([, b]) => b.group.position.x * end)
          .sort((u, v) => v - u);
        if (near.length > 1) varLine.position.x = near[1] * end;
      }
      // Goal scorer, auto camera: a tight shot that slowly circles the player while they celebrate.
      const hero = p.camera === "auto" && f.kind === "player" && !!subject && !p.replay;
      if (hero && subject) {
        const ang = (performance.now() / 1000) * 0.22;
        const hx = subject.x + Math.cos(ang) * 10;
        const hz = subject.z + Math.sin(ang) * 10;
        wantTarget.set(subject.x, 1.4, subject.z);
        // high enough to look over the teammates crowding round, low enough to feel close
        wantPos.set(Math.max(-L / 2 - 3, Math.min(L / 2 + 3, hx)), 5.5, Math.max(-W / 2 - 3, Math.min(W / 2 + 3, hz)));
      }
      const fov = hero ? 26 : cid === "goal-left" || cid === "goal-right" ? 52 : cid === "close" ? 38 : cid === "overhead" ? 40 : 32;
      if (cam.fov !== fov) {
        cam.fov = fov;
        cam.updateProjectionMatrix();
      }
      if (!reduceMotion && cid !== "overhead" && !hero) {
        // a slow, barely-there drift, like a camera operator holding the shot
        const tt = performance.now() / 1000;
        wantPos.x += Math.sin(tt * 0.21) * 1.2;
        wantPos.y += Math.sin(tt * 0.17) * 0.5;
      }
      const shotId = hero ? "hero" : cid;
      const jump = reduceMotion || lastCamera !== shotId;
      lastCamera = shotId;
      const k = jump ? 1 : 0.06;
      camPos.lerp(wantPos, k);
      camTarget.lerp(wantTarget, k);
      cam.position.copy(camPos);
      cam.lookAt(camTarget);
      renderer.render(scene, cam);
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.dispose();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose?.();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        (Array.isArray(mat) ? mat : mat ? [mat] : []).forEach((x) => {
          (x as THREE.MeshBasicMaterial).map?.dispose();
          x.dispose();
        });
      });
      el.removeChild(renderer.domElement);
    };
    // the scene is built once per tracking file; everything else is read live from props
  }, [props.tracking]);

  return (
    <div className="stadium3d" ref={host} aria-hidden="true">
      {(props.badge ?? (props.replay ? "REPLAY" : null)) && <div className="replay-badge">{props.badge ?? "REPLAY"}</div>}
    </div>
  );
}
