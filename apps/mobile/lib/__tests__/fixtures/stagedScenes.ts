/** A still scene the server built in stages, shared by the lib and render tests. */

/** 10 N at 30°, resolved: the vector, then its horizontal component, then its vertical one. */
export const RESOLVED = {
  type: "vector_sum",
  title: "Components",
  title_key: "components",
  bodies: [],
  vectors: [
    { anchor: [0, 0], dx: 8.66, dy: 5, label: "10 N", role: "force", stage: 0 },
    { anchor: [0, 0], dx: 8.66, dy: 0, label: "Fx = 8.66 N", role: "result", stage: 1 },
    { anchor: [8.66, 0], dx: 0, dy: 5, label: "Fy = 5 N", role: "result", stage: 2 },
  ],
  // The given angle comes with the given vector.
  angles: [{ vertex: [0, 0], start_deg: 0, end_deg: 30, label: "30°", role: "given", stage: 0 }],
  x_min: -1,
  x_max: 10,
  y_min: -1,
  y_max: 6,
  arrows: [],
};
