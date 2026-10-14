/**
 * A wave, stepped through the frames the server sampled over its fixed x
 * samples, looping. Nodes, antinodes, what holds the ends and the λ / A
 * measures are drawn around it; a still standing wave also shows its envelope.
 */
import { useMemo } from "react";
import { useWindowDimensions } from "react-native";
import { useTranslation } from "react-i18next";
import { Circle, DashPathEffect, Group, Path, Skia } from "@shopify/react-native-skia";
import { useDerivedValue } from "react-native-reanimated";

import { figureWidth } from "@/components/rich/figure";
import { PlaybackButton } from "@/components/rich/PlaybackButton";
import { usePlayback } from "@/components/rich/usePlayback";
import { linePath } from "@/components/rich/skia/paths";
import {
  DiagramFrame,
  useDiagramFont,
  useDiagramTitle,
} from "@/components/rich/diagrams/DiagramFrame";
import { DiagramLabel, MeasureLine, rectPath, segmentsPath } from "@/components/rich/diagrams/marks";
import type { WaveDiagramSpec } from "@/components/rich/diagrams/spec";
import { measureDiagramText } from "@/components/rich/diagrams/textWidth";
import {
  firstClearLabel,
  labelBox,
  labelHits,
  layoutMeasure,
  placeLabel,
  toScreen,
  worldTransform,
  worldViewportHeight,
  type LabelPlacement,
  type LabelSide,
  type Obstacle,
  type ScreenPoint,
  type Segment,
} from "@/lib/physics/optics";
import {
  describeWave,
  isStandingWave,
  sampleAt,
  waveCycleLength,
  waveEnvelope,
  waveHasPipe,
  waveSamplesAt,
} from "@/lib/physics/wave";
import { useTheme, withAlpha } from "@/lib/theme";

/**
 * One loop of the frames. Fixed rather than the real period, which ranges
 * from milliseconds (sound) to seconds (a rope): the shape and the way it
 * moves are the lesson, and the labels state the numbers.
 */
const WAVE_LOOP_MS = 2400;
const WAVE_STROKE = 2;
const NODE_RADIUS = 3;
const CLAMP_WIDTH = 7;
const PIPE_GAP = 10;
const GUIDE_OVERHANG = 4;
const MARK_GAP = 4;

export function WaveDiagram({ spec, content }: { spec: WaveDiagramSpec; content: string }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const { width: screenWidth } = useWindowDimensions();
  const width = figureWidth(screenWidth);
  const font = useDiagramFont();
  const title = useDiagramTitle(spec);
  const height = useMemo(() => worldViewportHeight(spec.bounds, width), [spec, width]);
  const transform = useMemo(() => worldTransform(spec.bounds, width, height), [height, spec, width]);
  // The title is its own text above the canvas, so the description does not repeat it.
  const description = useMemo(() => {
    const labels = spec.measures.flatMap((measure) => (measure.label ? [measure.label] : []));
    return spec.alt ?? describeWave(spec.wave, labels, t);
  }, [spec, t]);

  const scene = useMemo(() => {
    const { wave } = spec;
    const canvas = { width, height };
    const axis = transform.offsetY;
    const xs = wave.x.map((x) => toScreen(x, 0, transform).px);
    const first = xs[0];
    const last = xs[xs.length - 1];
    // Screen offsets, positive up, so the worklet only indexes and blends.
    const frames = wave.frames.map((frame) => frame.map((value) => value * transform.scale));
    const envelope = waveEnvelope(wave);
    const reach = Math.max(...envelope) * transform.scale;

    const envelopePath = Skia.Path.Make();
    for (const sign of [1, -1]) {
      envelope.forEach((value, index) => {
        const y = axis - sign * value * transform.scale;
        if (index === 0) envelopePath.moveTo(xs[index], y);
        else envelopePath.lineTo(xs[index], y);
      });
    }

    // What holds each end: a clamp, or the walls and cap of a pipe.
    const clampHalf = Math.max(reach + 8, 12);
    const clampBoxes = wave.ends.flatMap((end, index) =>
      end === "fixed"
        ? [{ x: index === 0 ? first - CLAMP_WIDTH : last, y: axis - clampHalf, width: CLAMP_WIDTH, height: clampHalf * 2 }]
        : [],
    );
    const clamps = clampBoxes.map((box) => rectPath(box.x, box.y, box.width, box.height));
    const hasPipe = waveHasPipe(wave);
    const wall = reach + PIPE_GAP;
    const pipeSegments: Segment[] = [];
    if (hasPipe) {
      pipeSegments.push(
        { x1: first, y1: axis - wall, x2: last, y2: axis - wall },
        { x1: first, y1: axis + wall, x2: last, y2: axis + wall },
      );
    }
    const capSegments: Segment[] = wave.ends.flatMap((end, index) => {
      if (!hasPipe || end !== "closed") return [];
      const x = index === 0 ? first : last;
      return [{ x1: x, y1: axis - wall, x2: x, y2: axis + wall }];
    });
    const pipe = segmentsPath(pipeSegments);
    const caps = segmentsPath(capSegments);

    const measures = spec.measures.map((vector) => layoutMeasure(vector, transform, canvas, measureDiagramText));
    // What a node's or antinode's letter must not sit on. The wave itself is
    // not on the list: it moves through everything between its crests.
    const obstacles: Obstacle[] = [
      ...measures.flatMap((measure) => [
        { x1: measure.from.px, y1: measure.from.py, x2: measure.to.px, y2: measure.to.py },
        ...(measure.label ? [labelBox(measure.label)] : []),
      ]),
      ...measures.map((measure) => ({ x: measure.from.px - 5, y: measure.from.py - 5, width: 10, height: 10 })),
      ...measures.map((measure) => ({ x: measure.to.px - 5, y: measure.to.py - 5, width: 10, height: 10 })),
      ...clampBoxes,
      ...pipeSegments,
      ...capSegments,
    ];
    /** A mark's letter on one side, centred or nudged clear of a clamp or a cap. */
    const sideCandidates = (text: string, textWidth: number, at: ScreenPoint, side: LabelSide, gap: number) => {
      const shift = textWidth / 2 + NODE_RADIUS + 1;
      return [0, shift, -shift].map((dx) =>
        placeLabel(text, textWidth, { px: at.px + dx, py: at.py }, side, gap, canvas),
      );
    };
    const clear = (label: LabelPlacement) => !labelHits(label, obstacles);

    const nodeText = t("rich.diagram_mark_node");
    const nodeWidth = measureDiagramText(nodeText);
    const nodePoints = wave.nodes.map((x) => toScreen(x, 0, transform));
    const nodeGap = NODE_RADIUS + MARK_GAP;
    // Every node's letter on the same side when that side has room for all.
    let nodeLabels: LabelPlacement[] | null = null;
    for (const side of ["below", "above"] as const) {
      const picks = nodePoints.map((at) => sideCandidates(nodeText, nodeWidth, at, side, nodeGap).find(clear));
      if (picks.every((pick): pick is LabelPlacement => pick !== undefined)) {
        nodeLabels = picks;
        break;
      }
    }
    nodeLabels ??= nodePoints.map((at) =>
      firstClearLabel(
        [
          ...sideCandidates(nodeText, nodeWidth, at, "below", nodeGap),
          ...sideCandidates(nodeText, nodeWidth, at, "above", nodeGap),
          ...(hasPipe ? [placeLabel(nodeText, nodeWidth, { px: at.px, py: axis + wall }, "below", 3, canvas)] : []),
        ],
        obstacles,
      ),
    );
    obstacles.push(...nodeLabels.map(labelBox));
    const nodes = nodePoints.map((at, index) => ({ at, label: nodeLabels[index] }));

    const antinodeText = t("rich.diagram_mark_antinode");
    const antinodeWidth = measureDiagramText(antinodeText);
    const antinodes = wave.antinodes.map((x) => {
      const px = toScreen(x, 0, transform).px;
      const half = sampleAt(wave.x, envelope, x) * transform.scale + GUIDE_OVERHANG;
      const top = { px, py: axis - half };
      const bottom = { px, py: axis + half };
      const label = firstClearLabel(
        [
          ...sideCandidates(antinodeText, antinodeWidth, top, "above", 3),
          ...sideCandidates(antinodeText, antinodeWidth, bottom, "below", 3),
          // In a pipe, past the walls.
          ...(hasPipe
            ? [
                placeLabel(antinodeText, antinodeWidth, { px, py: axis - wall }, "above", 3, canvas),
                placeLabel(antinodeText, antinodeWidth, { px, py: axis + wall }, "below", 3, canvas),
              ]
            : []),
        ],
        obstacles,
      );
      obstacles.push(labelBox(label));
      return { guide: linePath(px, top.py, px, bottom.py), label };
    });

    return {
      axis,
      xs,
      frames,
      cycle: waveCycleLength(wave.frames),
      axisLine: linePath(first, axis, last, axis),
      envelopePath,
      measures,
      nodes,
      antinodes,
      clamps,
      pipe: hasPipe ? pipe : null,
      caps,
    };
  }, [height, spec, t, transform, width]);

  const { progress, isPlaying, play, pause, reduceMotion } = usePlayback({
    duration: WAVE_LOOP_MS,
    animated: true,
    autoplay: true,
    loop: true,
    resetKey: content,
  });

  const { xs, frames, cycle, axis } = scene;
  const curve = useDerivedValue(() => {
    const ys = waveSamplesAt(frames, cycle, progress.value);
    const path = Skia.Path.Make();
    for (let i = 0; i < xs.length; i += 1) {
      if (i === 0) path.moveTo(xs[i], axis - ys[i]);
      else path.lineTo(xs[i], axis - ys[i]);
    }
    return path;
  });

  const standing = isStandingWave(spec.wave);
  // A still frame is a moment of the motion; the envelope shows the rest of it.
  const showEnvelope = standing && !isPlaying;
  const markers = [
    "diagram-wave",
    ...spec.wave.nodes.map(() => "diagram-node"),
    ...spec.wave.antinodes.map(() => "diagram-antinode"),
    ...spec.wave.ends.filter((end) => end !== "none").map((end) => `diagram-end-${end}`),
    ...spec.measures.map(() => "diagram-measure"),
    ...(showEnvelope ? ["diagram-envelope"] : []),
    ...(reduceMotion === true ? ["diagram-static"] : []),
  ];

  return (
    <DiagramFrame
      testID="wave-canvas"
      title={title}
      description={description}
      width={width}
      height={height}
      markers={markers}
      footer={
        <PlaybackButton
          testID="wave"
          isPlaying={isPlaying}
          onPlay={play}
          onPause={pause}
          playLabel={t("rich.diagram_wave_play_a11y")}
          pauseLabel={t("rich.diagram_wave_pause_a11y")}
        />
      }
    >
      <Group clip={Skia.XYWHRect(0, 0, width, height)}>
        <Path path={scene.axisLine} color={theme.textTertiary} style="stroke" strokeWidth={1} />
        {scene.pipe ? (
          <>
            <Path path={scene.pipe} color={theme.textSecondary} style="stroke" strokeWidth={2} strokeCap="round" />
            <Path path={scene.caps} color={theme.textSecondary} style="stroke" strokeWidth={3} strokeCap="round" />
          </>
        ) : null}
        {scene.clamps.map((path, index) => (
          <Path key={`clamp-${index}`} path={path} color={theme.textSecondary} />
        ))}
        {scene.antinodes.map((antinode, index) => (
          <Path
            key={`antinode-${index}`}
            path={antinode.guide}
            color={withAlpha(theme.textTertiary, 0.7)}
            style="stroke"
            strokeWidth={1}
          >
            <DashPathEffect intervals={[2, 3]} />
          </Path>
        ))}
        {showEnvelope ? (
          <Path path={scene.envelopePath} color={withAlpha(theme.primary, 0.35)} style="stroke" strokeWidth={1}>
            <DashPathEffect intervals={[3, 3]} />
          </Path>
        ) : null}
        {scene.measures.map((measure, index) => (
          <MeasureLine key={`measure-${index}`} layout={measure} color={theme.textSecondary} />
        ))}
        <Path path={curve} color={theme.primary} style="stroke" strokeWidth={WAVE_STROKE} strokeJoin="round" strokeCap="round" />
        {scene.nodes.map((node, index) => (
          <Circle key={`node-${index}`} cx={node.at.px} cy={node.at.py} r={NODE_RADIUS} color={theme.text} />
        ))}
      </Group>
      {font ? (
        <>
          {scene.nodes.map((node, index) => (
            <DiagramLabel key={`node-label-${index}`} label={node.label} font={font} color={theme.textSecondary} theme={theme} />
          ))}
          {scene.antinodes.map((antinode, index) => (
            <DiagramLabel
              key={`antinode-label-${index}`}
              label={antinode.label}
              font={font}
              color={theme.textTertiary}
              theme={theme}
            />
          ))}
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
