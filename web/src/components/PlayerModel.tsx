import { useEffect, useRef } from "react";
import * as THREE from "three";
import { animalOf } from "../lib/animals";
import { kitOf } from "../lib/kit";
import type { Team } from "../lib/types";
import { makeCharacter } from "./characters";

/** The phone's 3D look at one player: their chibi character on a little turntable. It turns slowly by itself and
 *  follows a finger (drag left/right). Loaded only when a phone shows a player, so phones that never do skip three.js.
 *  Calm on purpose: slow turn, no camera moves, and it stops turning for viewers who prefer reduced motion. */
export default function PlayerModel({ playerId, teams, height = 220, celebrate = false }: {
  playerId: string; teams: Team[]; height?: number; celebrate?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const cel = useRef(celebrate);
  cel.current = celebrate;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight("#fff6e0", "#24405f", 1.6));
    const sun = new THREE.DirectionalLight("#ffffff", 1.6);
    sun.position.set(3, 6, 4);
    scene.add(sun);
    const cam = new THREE.PerspectiveCamera(28, 1, 0.1, 50);
    cam.position.set(0, 1.25, 6.2);
    cam.lookAt(0, 0.95, 0);

    const kit = kitOf(playerId, teams);
    const char = makeCharacter(animalOf(playerId), kit.primary, kit.secondary);
    const turn = new THREE.Group();
    turn.add(char.root);
    // shirt number on the back, like a real kit
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d")!;
    g.fillStyle = kit.secondary;
    g.font = "900 84px system-ui, sans-serif";
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(playerId.split("-")[1], 64, 70);
    const num = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.42), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true }));
    num.position.set(-0.36, 0.86, 0); // local -x is the back
    num.rotation.y = -Math.PI / 2;
    char.body.add(num);
    // a soft disc to stand on
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.95, 0.95, 0.06, 40), new THREE.MeshStandardMaterial({ color: "#16273f", roughness: 0.9 }));
    disc.position.y = -0.03;
    scene.add(disc, turn);

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let angle = -Math.PI / 2; // start facing the viewer (local +x is the face; turning -90° points it at the camera)
    let spin = reduce ? 0 : 0.35; // rad/s
    let drag: { x: number; a: number } | null = null;
    const down = (e: PointerEvent) => {
      drag = { x: e.clientX, a: angle };
      el.setPointerCapture(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      if (drag) angle = drag.a + (e.clientX - drag.x) * 0.012;
    };
    const up = () => {
      drag = null;
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);

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
    let last = performance.now();
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const now = performance.now();
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (!drag) angle += spin * dt;
      turn.rotation.y = angle;
      // idle: a gentle breath; celebrating: arms up and a little hop
      const t = now / 1000;
      const party = cel.current && !reduce;
      const beat = Math.abs(Math.sin(t * Math.PI * 1.8));
      char.body.position.y = party ? 0 : Math.sin(t * 2) * 0.015;
      char.root.position.y = party ? beat * 0.25 : 0;
      char.arms[0].rotation.x = 0.25 + (party ? 1.6 + 0.3 * beat : 0);
      char.arms[1].rotation.x = -0.25 - (party ? 1.6 + 0.3 * beat : 0);
      renderer.render(scene, cam);
    };
    draw();
    if (reduce) spin = 0;

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      renderer.dispose();
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh) {
          o.geometry.dispose();
          (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
        }
      });
      el.removeChild(renderer.domElement);
    };
  }, [playerId, teams]);

  return <div ref={host} className="player-model" style={{ height }} role="img" aria-label="3D character, drag to turn" />;
}

/** Small face pictures for a team grid, drawn once with one renderer and handed back as image URLs. */
export function renderPortraits(ids: string[], teams: Team[], size = 160): Record<string, string> {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(size, size, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const cam = new THREE.PerspectiveCamera(24, 1, 0.1, 50);
  cam.position.set(0.15, 1.5, 4.0);
  cam.lookAt(0, 1.25, 0);
  const out: Record<string, string> = {};
  for (const id of ids) {
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight("#fff6e0", "#24405f", 1.7));
    const sun = new THREE.DirectionalLight("#ffffff", 1.4);
    sun.position.set(2, 5, 4);
    scene.add(sun);
    const kit = kitOf(id, teams);
    const char = makeCharacter(animalOf(id), kit.primary, kit.secondary);
    char.root.rotation.y = -Math.PI / 2 + 0.3; // face the camera, a little turned
    scene.add(char.root);
    renderer.render(scene, cam);
    out[id] = renderer.domElement.toDataURL("image/png");
    scene.traverse((o) => {
      if (o instanceof THREE.Mesh) o.geometry.dispose();
    });
  }
  renderer.dispose();
  renderer.forceContextLoss();
  return out;
}
