/** Camera choices for the 3D view (kept apart from Stadium3D so phones never load the 3D library). */
export type CameraId = "auto" | "broadcast" | "opposite" | "goal-left" | "goal-right" | "close" | "overhead";
export const CAMERAS: { id: CameraId | "tactical"; label: string }[] = [
  { id: "auto", label: "Auto" },
  { id: "broadcast", label: "Main stand" },
  { id: "opposite", label: "Far side" },
  { id: "goal-left", label: "Left goal" },
  { id: "goal-right", label: "Right goal" },
  { id: "close", label: "Close-up" },
  { id: "overhead", label: "Overhead (VAR)" },
  { id: "tactical", label: "Tactical 2D" },
];
