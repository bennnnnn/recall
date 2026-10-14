/**
 * A static ray diagram: the element at x = 0 on the optical axis, the object
 * and its image, and the rays exactly as the server traced them.
 */
import { useMemo } from "react";
import { useWindowDimensions } from "react-native";
import { useTranslation } from "react-i18next";
import { DashPathEffect, Group, Path, Skia, type SkPath } from "@shopify/react-native-skia";

import { figureWidth } from "@/components/rich/figure";
import {
  appendArrowHead,
  arrowHeadPath,
  arrowPath,
  arrowShaftPath,
  linePath,
  pointsPath,
} from "@/components/rich/skia/paths";
import {
  DiagramFrame,
  useDiagramFont,
  useDiagramTitle,
} from "@/components/rich/diagrams/DiagramFrame";
import { DiagramLabel, MeasureLine, rectPath, segmentsPath } from "@/components/rich/diagrams/marks";
import type { RayDiagramSpec } from "@/components/rich/diagrams/spec";
import { measureDiagramText } from "@/components/rich/diagrams/textWidth";
import {
  angleArc,
  angleLabel,
  describeOptics,
  elementExtent,
  firstClearLabel,
  focalPoints,
  hatchSegments,
  labelBox,
  layoutMeasure,
  mediumLabelSide,
  mirrorCurve,
  placeLabel,
  polylineSegments,
  RAY_HEAD,
  rayMarks,
  toScreen,
  worldTransform,
  worldViewportHeight,
  type LabelPlacement,
  type Obstacle,
  type OpticsArrow,
  type ScreenPoint,
  type Segment,
} from "@/lib/physics/optics";
import { useTheme, withAlpha, type Theme } from "@/lib/theme";

const ELEMENT_STROKE = 2;
const RAY_STROKE = 1.5;
const ARROW_STROKE = 2;
const ARROW_HEAD = 8;
const LENS_HEAD = 8;
const FOCUS_TICK = 4;
const LABEL_GAP = 5;
const MEDIUM_INSET = 8;

type ArrowPaths = { solid: SkPath | null; shaft: SkPath | null; head: SkPath | null };

/** An object or image standing on the axis; a virtual one is dashed, its head solid. */
function standingArrow(arrow: OpticsArrow, axis: number, x: number, scale: number): ArrowPaths {
  const length = Math.abs(arrow.height) * scale;
  const uy = arrow.height > 0 ? -1 : 1;
  const head = Math.min(ARROW_HEAD, length * 0.45);
  if (!arrow.virtual) return { solid: arrowPath(x, axis, 0, uy, length, head, "filled"), shaft: null, head: null };
  return {
    solid: null,
    shaft: arrowShaftPath(x, axis, 0, uy, Math.max(0, length - head * 0.6)),
    head: arrowHeadPath(x, axis, 0, uy, length, head, "filled"),
  };
}

function ArrowShape({ paths, color }: { paths: ArrowPaths; color: string }) {
  return (
    <>
      {paths.solid ? (
        <>
          <Path path={paths.solid} color={color} style="stroke" strokeWidth={ARROW_STROKE} strokeJoin="round" strokeCap="round" />
          <Path path={paths.solid} color={color} style="fill" />
        </>
      ) : null}
      {paths.shaft ? (
        <Path path={paths.shaft} color={color} style="stroke" strokeWidth={ARROW_STROKE}>
          <DashPathEffect intervals={[4, 3]} />
        </Path>
      ) : null}
      {paths.head ? (
        <>
          <Path path={paths.head} color={color} style="stroke" strokeWidth={1} strokeJoin="round" />
          <Path path={paths.head} color={color} style="fill" />
        </>
      ) : null}
    </>
  );
}

export function RayDiagram({ spec }: { spec: RayDiagramSpec }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const width = figureWidth(screenWidth);
  const font = useDiagramFont();
  const title = useDiagramTitle(spec);
  const height = useMemo(() => worldViewportHeight(spec.bounds, width), [spec, width]);
  const transform = useMemo(() => worldTransform(spec.bounds, width, height), [height, spec, width]);
  // The title is its own text above the canvas, so the description does not repeat it.
  const description = useMemo(
    () => spec.alt ?? describeOptics(spec.optics, spec.angles, t),
    [spec, t],
  );

  const scene = useMemo(() => {
    const { optics } = spec;
    const canvas = { width, height };
    const rect = { x: 0, y: 0, width, height };
    const axis = transform.offsetY;
    const elementX = toScreen(0, 0, transform).px;
    const extent = elementExtent(optics, spec.bounds, transform, height);
    const interfaceKind = optics.element === "interface";

    // The element.
    let element: SkPath;
    let hatch: SkPath | null = null;
    let elementSegments: Segment[] = [];
    if (optics.element === "converging_lens" || optics.element === "diverging_lens") {
      element = linePath(elementX, extent.top, elementX, extent.bottom);
      elementSegments = [{ x1: elementX, y1: extent.top - LENS_HEAD, x2: elementX, y2: extent.bottom + LENS_HEAD }];
      // Out-turned heads converge light; in-turned heads spread it.
      const outward = optics.element === "converging_lens";
      appendArrowHead(element, elementX, extent.top, 0, outward ? -1 : 1, LENS_HEAD, "open");
      appendArrowHead(element, elementX, extent.bottom, 0, outward ? 1 : -1, LENS_HEAD, "open");
    } else if (interfaceKind) {
      element = linePath(0, axis, width, axis);
      // The boundary and its normal: an angle's label must not straddle either.
      elementSegments = [
        { x1: 0, y1: axis, x2: width, y2: axis },
        { x1: elementX, y1: 0, x2: elementX, y2: height },
      ];
    } else {
      const curve = mirrorCurve(optics.element, elementX, axis, extent.top, extent.bottom);
      element = pointsPath(curve);
      const hatches = hatchSegments(curve);
      hatch = segmentsPath(hatches);
      elementSegments = [...polylineSegments(curve), ...hatches];
    }

    const focus = focalPoints(optics).map((x) => toScreen(x, 0, transform).px);
    const focusTicks = segmentsPath(
      focus.map((px) => ({ x1: px, y1: axis - FOCUS_TICK, x2: px, y2: axis + FOCUS_TICK })),
    );

    const rays = optics.rays.map((ray) => {
      const points = ray.points.map((p) => toScreen(p.x, p.y, transform));
      const marks = ray.virtual ? [] : rayMarks(points, rect);
      const heads = Skia.Path.Make();
      for (const mark of marks) appendArrowHead(heads, mark.x, mark.y, mark.ux, mark.uy, RAY_HEAD, "filled");
      return { virtual: ray.virtual, line: pointsPath(points), heads, points, marks };
    });

    const arrowX = (arrow: OpticsArrow) => toScreen(arrow.x, 0, transform).px;
    const object = optics.object ? standingArrow(optics.object, axis, arrowX(optics.object), transform.scale) : null;
    const image = optics.image ? standingArrow(optics.image, axis, arrowX(optics.image), transform.scale) : null;

    const measures = spec.measures.map((vector) => layoutMeasure(vector, transform, canvas, measureDiagramText));

    // Labels go where no ray, mark or other label is: each candidate in turn,
    // and every label placed becomes something the next one avoids.
    const obstacles: Obstacle[] = [
      ...rays.flatMap((ray) => polylineSegments(ray.points)),
      ...rays.flatMap((ray) => ray.marks.map((m) => ({ x: m.x - RAY_HEAD, y: m.y - RAY_HEAD, width: RAY_HEAD * 2, height: RAY_HEAD * 2 }))),
      ...elementSegments,
      ...[optics.object, optics.image].flatMap((arrow) =>
        arrow ? [{ x1: arrowX(arrow), y1: axis, x2: arrowX(arrow), y2: axis - arrow.height * transform.scale }] : [],
      ),
      ...measures.flatMap((measure) => (measure.label ? [labelBox(measure.label)] : [])),
    ];
    const place = (candidates: LabelPlacement[]) => {
      const label = firstClearLabel(candidates, obstacles);
      obstacles.push(labelBox(label));
      return label;
    };

    const standingLabel = (arrow: OpticsArrow | undefined) => {
      if (!arrow?.label) return null;
      const width = measureDiagramText(arrow.label);
      const tip: ScreenPoint = { px: arrowX(arrow), py: axis - arrow.height * transform.scale };
      const foot: ScreenPoint = { px: tip.px, py: axis };
      const upright = arrow.height > 0;
      // Past the tip first, then beside it, then on the far side of the axis.
      return place([
        placeLabel(arrow.label, width, tip, upright ? "above" : "below", LABEL_GAP, canvas),
        placeLabel(arrow.label, width, tip, "right", LABEL_GAP, canvas),
        placeLabel(arrow.label, width, tip, "left", LABEL_GAP, canvas),
        placeLabel(arrow.label, width, foot, upright ? "below" : "above", LABEL_GAP, canvas),
      ]);
    };
    const objectLabel = standingLabel(optics.object);
    const imageLabel = standingLabel(optics.image);

    const focusText = t("rich.diagram_mark_focus");
    const focusWidth = measureDiagramText(focusText);
    const focusLabels = focus.map((px) =>
      place([
        placeLabel(focusText, focusWidth, { px, py: axis + FOCUS_TICK }, "below", 3, canvas),
        placeLabel(focusText, focusWidth, { px, py: axis - FOCUS_TICK }, "above", 3, canvas),
      ]),
    );

    const angles = spec.angles.map((angle) => {
      const arc = angleArc(angle, transform);
      const path = pointsPath(arc.points);
      if (angle.arrow) {
        const end = arc.points[arc.points.length - 1];
        appendArrowHead(path, end.px, end.py, arc.endDirection.ux, arc.endDirection.uy, 6, "open");
      }
      obstacles.push(...polylineSegments(arc.points));
      return { path, role: angle.role, label: angle.label };
    });
    const angleLabels = angles.map((angle, index) => {
      if (!angle.label) return null;
      const label = angleLabel(
        spec.angles[index],
        angle.label,
        measureDiagramText(angle.label),
        transform,
        obstacles,
        canvas,
      );
      obstacles.push(labelBox(label));
      return label;
    });

    let media: LabelPlacement[] = [];
    if (interfaceKind && optics.media) {
      const rayPoints = rays.map((ray) => ray.points);
      media = optics.media.map((name, index) => {
        const top = index === 0;
        const nameWidth = measureDiagramText(name);
        const side = mediumLabelSide(rayPoints, top, axis, width);
        const left = side === "left" ? MEDIUM_INSET : width - MEDIUM_INSET - nameWidth;
        return placeLabel(name, nameWidth, { px: left + nameWidth / 2, py: axis }, top ? "above" : "below", 7, canvas);
      });
    }

    return {
      axis,
      elementX,
      extent,
      element,
      hatch,
      focusTicks,
      rays,
      object,
      image,
      angles,
      angleLabels,
      measures,
      objectLabel,
      imageLabel,
      focusLabels,
      media,
    };
  }, [height, spec, t, transform, width]);

  const markers = useMemo(() => {
    const { optics } = spec;
    return [
      `diagram-element-${optics.element}`,
      ...focalPoints(optics).map(() => "diagram-focus"),
      ...(optics.object ? ["diagram-object"] : []),
      ...(optics.image ? [optics.image.virtual ? "diagram-image-virtual" : "diagram-image"] : []),
      ...optics.rays.map((ray) => (ray.virtual ? "diagram-ray-virtual" : "diagram-ray")),
      ...spec.angles.map((angle) => (angle.role === "result" ? "diagram-angle-result" : "diagram-angle")),
      ...scene.media.map(() => "diagram-medium"),
      ...spec.measures.map(() => "diagram-measure"),
    ];
  }, [scene, spec]);

  const rayColor = theme.graphSeries[2];
  const faintRay = withAlpha(rayColor, 0.6);
  const interfaceKind = spec.optics.element === "interface";
  return (
    <DiagramFrame
      testID="rays-canvas"
      title={title}
      description={description}
      width={width}
      height={height}
      markers={markers}
    >
      <Group clip={Skia.XYWHRect(0, 0, width, height)}>
        {interfaceKind ? (
          <>
            <Path path={rectPath(0, 0, width, scene.axis)} color={withAlpha(theme.textTertiary, 0.07)} />
            <Path
              path={rectPath(0, scene.axis, width, height - scene.axis)}
              color={withAlpha(theme.primary, 0.1)}
            />
            <Path
              path={linePath(scene.elementX, 4, scene.elementX, height - 4)}
              color={theme.textTertiary}
              style="stroke"
              strokeWidth={1}
            >
              <DashPathEffect intervals={[4, 4]} />
            </Path>
          </>
        ) : (
          <Path
            path={linePath(0, scene.axis, width, scene.axis)}
            color={theme.textTertiary}
            style="stroke"
            strokeWidth={1}
          />
        )}
        <Path
          path={scene.element}
          color={theme.textSecondary}
          style="stroke"
          strokeWidth={interfaceKind ? 1.5 : ELEMENT_STROKE}
          strokeCap="round"
          strokeJoin="round"
        />
        {scene.hatch ? (
          <Path path={scene.hatch} color={theme.textTertiary} style="stroke" strokeWidth={1} />
        ) : null}
        <Path path={scene.focusTicks} color={theme.textSecondary} style="stroke" strokeWidth={1.5} />
        {scene.rays.map((ray, index) =>
          ray.virtual ? (
            <Path key={`ray-${index}`} path={ray.line} color={faintRay} style="stroke" strokeWidth={1}>
              <DashPathEffect intervals={[4, 4]} />
            </Path>
          ) : (
            <Group key={`ray-${index}`}>
              <Path path={ray.line} color={rayColor} style="stroke" strokeWidth={RAY_STROKE} strokeJoin="round" />
              <Path path={ray.heads} color={rayColor} style="fill" />
            </Group>
          ),
        )}
        {scene.object ? <ArrowShape paths={scene.object} color={theme.text} /> : null}
        {scene.image ? <ArrowShape paths={scene.image} color={theme.primary} /> : null}
        {scene.angles.map((angle, index) => (
          <Path
            key={`angle-${index}`}
            path={angle.path}
            color={angleColor(angle.role, theme)}
            style="stroke"
            strokeWidth={angle.role === "result" ? 2 : 1.5}
            strokeCap="round"
          />
        ))}
        {scene.measures.map((measure, index) => (
          <MeasureLine key={`measure-${index}`} layout={measure} color={theme.textSecondary} />
        ))}
      </Group>
      {font ? (
        <>
          {scene.media.map((label, index) => (
            <DiagramLabel key={`medium-${index}`} label={label} font={font} color={theme.textSecondary} theme={theme} />
          ))}
          {scene.focusLabels.map((label, index) => (
            <DiagramLabel key={`focus-${index}`} label={label} font={font} color={theme.textSecondary} theme={theme} />
          ))}
          {scene.objectLabel ? (
            <DiagramLabel label={scene.objectLabel} font={font} color={theme.text} theme={theme} />
          ) : null}
          {scene.imageLabel ? (
            <DiagramLabel label={scene.imageLabel} font={font} color={theme.primary} theme={theme} />
          ) : null}
          {scene.angleLabels.map((label, index) =>
            label ? (
              <DiagramLabel
                key={`angle-label-${index}`}
                label={label}
                font={font}
                color={angleColor(scene.angles[index].role, theme)}
                theme={theme}
              />
            ) : null,
          )}
          {scene.measures.map((measure, index) =>
            measure.label ? (
              <DiagramLabel
                key={`measure-label-${index}`}
                label={measure.label}
                font={font}
                color={theme.textSecondary}
                theme={theme}
              />
            ) : null,
          )}
        </>
      ) : null}
    </DiagramFrame>
  );
}

function angleColor(role: "given" | "result", theme: Theme): string {
  return role === "result" ? theme.primary : theme.textSecondary;
}
