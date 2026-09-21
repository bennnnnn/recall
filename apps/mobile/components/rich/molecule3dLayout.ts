import type { MolAtom, MolGeometry } from "@/lib/chemistry/molecule3dFence";

export const MOLECULE_PREVIEW_HEIGHT = 280;

export type MoleculeStyle = "ball-stick" | "spacefill" | "wireframe";

const VIEW_PAD = 36;

const CPK: Record<string, string> = {
  H: "#c5cdd8",
  C: "#3d3d3d",
  N: "#3b6bdb",
  O: "#e31c1c",
  F: "#3aaa3a",
  P: "#e07000",
  S: "#d4b41c",
  Cl: "#1f9a1f",
  Br: "#a62929",
  I: "#940094",
};

const LIGHT_ATOMS = new Set(["H", "F", "S", "Cl"]);

const RADIUS: Record<string, number> = {
  H: 0.32,
  C: 0.7,
  N: 0.65,
  O: 0.6,
  F: 0.5,
  P: 0.9,
  S: 0.88,
  Cl: 0.79,
  Br: 0.94,
  I: 1.15,
};

export function atomColor(element: string): string {
  return CPK[element] ?? "#c45c9a";
}

export function atomLabelColor(element: string): string {
  return LIGHT_ATOMS.has(element) ? "#1a1a1a" : "#fff";
}

function atomRadius(element: string): number {
  return RADIUS[element] ?? 0.7;
}

function project(atom: MolAtom, yaw: number, pitch: number) {
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const x = atom.x * cosYaw + atom.z * sinYaw;
  const z = -atom.x * sinYaw + atom.z * cosYaw;
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  return {
    x,
    y: atom.y * cosPitch - z * sinPitch,
    z: atom.y * sinPitch + z * cosPitch,
  };
}

export function layoutMolecule(
  geometry: MolGeometry,
  yaw: number,
  pitch: number,
  width: number,
  height: number,
  style: MoleculeStyle,
) {
  const atomScale = style === "spacefill" ? 0.72 : style === "wireframe" ? 0.2 : 0.32;
  const projected = geometry.atoms.map((atom) => project(atom, yaw, pitch));
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (let index = 0; index < projected.length; index++) {
    const point = projected[index]!;
    const radius = atomRadius(geometry.atoms[index]!.el) * atomScale;
    minX = Math.min(minX, point.x - radius);
    maxX = Math.max(maxX, point.x + radius);
    minY = Math.min(minY, point.y - radius);
    maxY = Math.max(maxY, point.y + radius);
  }

  const span = Math.max(maxX - minX, maxY - minY, 0.8);
  const scale = (Math.min(width, height) - VIEW_PAD * 2) / span;
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const atoms = projected.map((point, index) => ({
    index,
    element: geometry.atoms[index]!.el,
    x: (point.x - centerX) * scale + width / 2,
    y: (centerY - point.y) * scale + height / 2,
    z: point.z,
    radius: Math.max(
      3,
      atomRadius(geometry.atoms[index]!.el) * scale * atomScale,
    ),
  }));
  const depthOrder = atoms
    .map((_, index) => index)
    .sort((left, right) => atoms[left]!.z - atoms[right]!.z);
  return { atoms, depthOrder };
}

export function bondOffset(dx: number, dy: number, distance: number, magnitude: number) {
  return {
    x: (-dy / distance) * magnitude,
    y: (dx / distance) * magnitude,
  };
}
