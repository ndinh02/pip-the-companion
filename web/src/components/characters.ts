import * as THREE from "three";
import type { Animal } from "../lib/animals";

/** Chibi footballers: a big round animal head on a small body in the team kit. Built from simple shapes so the
 *  whole squad stays light enough for a laptop. Local +x is "forward" (the face), +y is up. */

export interface Character {
  root: THREE.Group;
  legs: [THREE.Object3D, THREE.Object3D];
  arms: [THREE.Object3D, THREE.Object3D];
  body: THREE.Group; // bobs while running
}

const mat = (color: string, rough = 0.75) => new THREE.MeshStandardMaterial({ color, roughness: rough });
const sphere = (r: number, m: THREE.Material, w = 16, h = 12) => new THREE.Mesh(new THREE.SphereGeometry(r, w, h), m);

const HEAD: Record<Animal, { fur: string; face?: string; nose: string }> = {
  penguin: { fur: "#2b3242", face: "#f4f1ea", nose: "#f2a33a" },
  bear: { fur: "#8a5a3c", face: "#dcb48c", nose: "#2a1d16" },
  dog: { fur: "#c9965f", face: "#f3e6d2", nose: "#2a1d16" },
  rabbit: { fur: "#f3f0ea", face: "#ffffff", nose: "#f19aa8" },
  fox: { fur: "#e07a2e", face: "#fbf3e7", nose: "#2a1d16" },
  tiger: { fur: "#f2a03d", face: "#fbf3e7", nose: "#c45a6a" },
  elephant: { fur: "#9aa6b2", face: "#b6c0ca", nose: "#9aa6b2" },
};

const black = mat("#141414", 0.4);
const white = new THREE.MeshBasicMaterial({ color: "#ffffff" });
const blush = new THREE.MeshBasicMaterial({ color: "#ff9fb0", transparent: true, opacity: 0.55 });

function addFace(head: THREE.Group, a: Animal, r: number) {
  const c = HEAD[a];
  // eyes with a highlight, rosy cheeks
  for (const side of [-1, 1]) {
    const eye = sphere(r * 0.12, black, 10, 8);
    eye.position.set(r * 0.86, r * 0.12, side * r * 0.36);
    eye.scale.set(0.6, 1.15, 1);
    const shine = sphere(r * 0.045, white, 6, 6);
    shine.position.set(r * 0.95, r * 0.2, side * r * 0.34);
    const cheek = new THREE.Mesh(new THREE.CircleGeometry(r * 0.14, 14), blush);
    cheek.position.set(r * 0.88, -r * 0.16, side * r * 0.56);
    cheek.rotation.y = Math.PI / 2 + side * 0.5;
    head.add(eye, shine, cheek);
  }
  // muzzle / face patch
  if (c.face && a !== "elephant") {
    const face = sphere(r * (a === "penguin" ? 0.78 : 0.42), mat(c.face));
    face.position.set(r * (a === "penguin" ? 0.32 : 0.7), -r * (a === "penguin" ? 0.05 : 0.22), 0);
    face.scale.set(a === "penguin" ? 0.7 : 0.75, a === "penguin" ? 0.95 : 0.7, a === "penguin" ? 1.05 : 0.95);
    head.add(face);
  }
  // nose / beak / trunk
  if (a === "penguin") {
    const beak = new THREE.Mesh(new THREE.ConeGeometry(r * 0.13, r * 0.32, 10), mat(c.nose, 0.5));
    beak.rotation.z = -Math.PI / 2;
    beak.position.set(r * 1.05, -r * 0.12, 0);
    head.add(beak);
  } else if (a === "elephant") {
    const trunk = new THREE.Mesh(new THREE.CapsuleGeometry(r * 0.13, r * 0.55, 4, 8), mat(c.fur));
    trunk.position.set(r * 0.98, -r * 0.4, 0);
    trunk.rotation.z = 0.35;
    head.add(trunk);
  } else {
    const nose = sphere(r * (a === "rabbit" ? 0.07 : 0.1), mat(c.nose, 0.4), 10, 8);
    nose.position.set(r * (a === "fox" || a === "dog" ? 1.06 : 0.98), -r * 0.12, 0);
    head.add(nose);
  }
  // ears
  const fur = mat(c.fur);
  for (const side of [-1, 1]) {
    let ear: THREE.Object3D | null = null;
    if (a === "bear" || a === "tiger") {
      ear = sphere(r * 0.24, fur, 12, 10);
      ear.position.set(-r * 0.05, r * 0.8, side * r * 0.6);
    } else if (a === "fox") {
      ear = new THREE.Mesh(new THREE.ConeGeometry(r * 0.26, r * 0.55, 4), fur);
      ear.position.set(0, r * 0.95, side * r * 0.5);
      ear.rotation.x = side * 0.35;
      const tip = new THREE.Mesh(new THREE.ConeGeometry(r * 0.12, r * 0.22, 4), black);
      tip.position.set(0, r * 1.15, side * r * 0.57);
      tip.rotation.x = side * 0.35;
      head.add(tip);
    } else if (a === "rabbit") {
      ear = new THREE.Mesh(new THREE.CapsuleGeometry(r * 0.15, r * 0.85, 4, 10), fur);
      ear.position.set(-r * 0.05, r * 1.25, side * r * 0.3);
      ear.rotation.x = side * 0.18;
      const inner = new THREE.Mesh(new THREE.CapsuleGeometry(r * 0.07, r * 0.6, 4, 8), mat("#f7b6c2"));
      inner.position.set(r * 0.09, r * 1.25, side * r * 0.3);
      inner.rotation.x = side * 0.18;
      head.add(inner);
    } else if (a === "dog") {
      ear = sphere(r * 0.3, mat("#7a5230"), 12, 10);
      ear.scale.set(0.55, 1.2, 0.45);
      ear.position.set(-r * 0.05, r * 0.15, side * r * 0.95);
    } else if (a === "elephant") {
      ear = new THREE.Mesh(new THREE.CircleGeometry(r * 0.62, 20), new THREE.MeshStandardMaterial({ color: c.fur, side: THREE.DoubleSide }));
      ear.position.set(-r * 0.15, r * 0.05, side * r * 0.95);
      ear.rotation.y = side * 0.35;
    }
    if (ear) head.add(ear);
  }
  // tiger stripes
  if (a === "tiger") {
    for (const dz of [-0.22, 0, 0.22]) {
      const stripe = new THREE.Mesh(new THREE.BoxGeometry(r * 0.08, r * 0.32, r * 0.06), black);
      stripe.position.set(r * 0.62, r * 0.62, dz * r);
      stripe.rotation.z = 0.5;
      head.add(stripe);
    }
  }
}

/** Build one chibi player. Height about 1.9 m in pitch units (a bit larger than life, so they read on TV). */
export function makeCharacter(animal: Animal, shirt: string, shorts: string): Character {
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const shirtM = mat(shirt, 0.65);
  const shortsM = mat(shorts, 0.75);
  const furM = mat(HEAD[animal].fur);

  // legs with little boots
  const legs: THREE.Object3D[] = [];
  for (const side of [-1, 1]) {
    const leg = new THREE.Group();
    const thigh = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.1, 0.42, 8), furM);
    thigh.position.y = -0.21;
    const boot = sphere(0.14, black, 10, 8);
    boot.scale.set(1.5, 0.7, 1);
    boot.position.set(0.06, -0.44, 0);
    leg.add(thigh, boot);
    leg.position.set(0, 0.5, side * 0.15);
    root.add(leg);
    legs.push(leg);
  }
  // round tummy in the shirt, shorts below
  const torso = sphere(0.36, shirtM, 18, 14);
  torso.scale.set(0.9, 1.0, 1.0);
  torso.position.y = 0.82;
  const pants = new THREE.Mesh(new THREE.CylinderGeometry(0.31, 0.29, 0.22, 14), shortsM);
  pants.position.y = 0.55;
  body.add(torso, pants);
  // stubby arms
  const arms: THREE.Object3D[] = [];
  for (const side of [-1, 1]) {
    const arm = new THREE.Group();
    const sleeve = new THREE.Mesh(new THREE.CapsuleGeometry(0.085, 0.26, 4, 8), shirtM);
    sleeve.position.y = -0.17;
    const paw = sphere(0.09, furM, 8, 6);
    paw.position.y = -0.36;
    arm.add(sleeve, paw);
    arm.position.set(0, 0.98, side * 0.37);
    arm.rotation.x = -side * 0.25;
    body.add(arm);
    arms.push(arm);
  }
  // the big head
  const r = 0.46;
  const head = new THREE.Group();
  head.add(sphere(r, furM, 22, 18));
  addFace(head, animal, r);
  head.position.y = 1.48;
  body.add(head);
  return { root, legs: [legs[0], legs[1]], arms: [arms[0], arms[1]], body };
}
