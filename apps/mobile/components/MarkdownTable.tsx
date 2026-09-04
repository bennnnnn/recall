import {
  Children,
  ReactElement,
  ReactNode,
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useMemo,
  useState,
} from "react";
import {
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";

import { Theme, useTheme } from "@/lib/theme";

type CellProps = { isLast?: boolean };

type RowProps = CellProps;

type TableLayout = {
  columnWidth: number;
};

const TableLayoutContext = createContext<TableLayout>({
  columnWidth: 120,
});

const TABLE_H_PAD = 32;
/** Wide enough that a 3-col ChatGPT-style grid pans instead of squeezing. */
const MIN_COL_WIDTH = 168;

export function resolveFrozenRowHeight(left?: number, right?: number): number {
  return Math.max(left ?? 0, right ?? 0);
}

export function tableColumnWidth(viewportWidth: number, columns: number): number {
  const colCount = Math.max(1, columns);
  const available = Math.max(200, viewportWidth);
  return Math.max(MIN_COL_WIDTH, available / colCount);
}

export function tableShouldFreezeFirstColumn(
  columns: number,
  viewportWidth: number,
  columnWidth: number,
): boolean {
  return columns >= 3 && columnWidth * columns > viewportWidth + 1;
}

function collectTableRows(children: ReactNode): ReactElement[] {
  const rows: ReactElement[] = [];
  for (const child of Children.toArray(children)) {
    if (!isValidElement(child)) continue;
    if (child.type === MarkdownTableRow) {
      rows.push(child);
      continue;
    }
    const nested = (child.props as { children?: ReactNode }).children;
    if (nested != null) {
      rows.push(...collectTableRows(nested));
    }
  }
  return rows;
}

function mapCells(children: ReactNode) {
  const cells = Children.toArray(children);
  return cells.map((child, index) => {
    if (!isValidElement<CellProps>(child)) return child;
    return cloneElement(child, { isLast: index === cells.length - 1 });
  });
}

function mapRows(children: ReactNode) {
  const rows = Children.toArray(children);
  return rows.map((child, index) => {
    if (!isValidElement<RowProps>(child)) return child;
    return cloneElement(child as ReactElement<RowProps>, {
      isLast: index === rows.length - 1,
    });
  });
}

type Props = {
  nodeKey: string;
  columns: number;
  children: ReactNode;
};

export function MarkdownTable({ nodeKey, columns, children }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { width: screenWidth } = useWindowDimensions();
  const fallbackW = Math.max(200, screenWidth - TABLE_H_PAD);
  const [viewportW, setViewportW] = useState(0);
  const layoutW = viewportW > 0 ? viewportW : fallbackW;
  const colCount = Math.max(1, columns);
  const columnWidth = tableColumnWidth(layoutW, colCount);
  const scrollable = columnWidth * colCount > layoutW + 1;

  const table = (
    <View
      key={nodeKey}
      style={[s.table, { width: columnWidth * colCount }]}
    >
      {mapRows(children)}
    </View>
  );

  const freezeFirst = tableShouldFreezeFirstColumn(colCount, layoutW, columnWidth);
  const rows = freezeFirst ? collectTableRows(children) : [];
  const restCols = Math.max(1, colCount - 1);

  return (
    <TableLayoutContext.Provider value={{ columnWidth }}>
      <View
        style={s.scrollWrap}
        onLayout={(e) => {
          const w = Math.round(e.nativeEvent.layout.width);
          if (w > 0 && Math.abs(w - viewportW) > 1) setViewportW(w);
        }}
      >
        {freezeFirst ? (
          <FrozenFirstColumnTable
            rows={rows}
            columnWidth={columnWidth}
            restCols={restCols}
            theme={theme}
            styles={s}
          />
        ) : (
          <ScrollView
            horizontal
            nestedScrollEnabled
            directionalLockEnabled
            bounces={false}
            overScrollMode="never"
            showsHorizontalScrollIndicator={false}
            scrollEnabled={scrollable}
            style={s.scroll}
            contentContainerStyle={
              scrollable ? { width: columnWidth * colCount } : undefined
            }
          >
            {table}
          </ScrollView>
        )}
      </View>
    </TableLayoutContext.Provider>
  );
}

function FrozenFirstColumnTable({
  rows,
  columnWidth,
  restCols,
  theme,
  styles: s,
}: {
  rows: ReactElement[];
  columnWidth: number;
  restCols: number;
  theme: Theme;
  styles: ReturnType<typeof makeStyles>;
}) {
  const [leftHeights, setLeftHeights] = useState<number[]>([]);
  const [rightHeights, setRightHeights] = useState<number[]>([]);

  return (
    <View style={s.freezeRow}>
      <View
        style={[
          s.frozenCol,
          { width: columnWidth, backgroundColor: theme.contentSurface },
        ]}
      >
        {rows.map((row, index) => {
          const cells = Children.toArray(
            (row.props as { children?: ReactNode }).children,
          );
          const height = resolveFrozenRowHeight(leftHeights[index], rightHeights[index]);
          return (
            <View
              key={`frozen-${index}`}
              style={[s.row, index === rows.length - 1 && s.rowLast, height ? { minHeight: height } : null]}
              onLayout={(e) => {
                const h = Math.round(e.nativeEvent.layout.height);
                setLeftHeights((prev) => {
                  if (prev[index] === h) return prev;
                  const next = prev.slice();
                  next[index] = h;
                  return next;
                });
              }}
            >
              {cells[0]}
            </View>
          );
        })}
      </View>
      <ScrollView
        horizontal
        nestedScrollEnabled
        directionalLockEnabled
        bounces={false}
        overScrollMode="never"
        showsHorizontalScrollIndicator={false}
        style={s.scroll}
        contentContainerStyle={{ width: columnWidth * restCols }}
      >
        <View>
          {rows.map((row, index) => {
            const cells = Children.toArray(
              (row.props as { children?: ReactNode }).children,
            );
            const height = resolveFrozenRowHeight(leftHeights[index], rightHeights[index]);
            return (
              <View
                key={`rest-${index}`}
                style={[
                  s.row,
                  index === rows.length - 1 && s.rowLast,
                  { width: columnWidth * restCols },
                  height ? { minHeight: height } : null,
                ]}
                onLayout={(e) => {
                  const h = Math.round(e.nativeEvent.layout.height);
                  setRightHeights((prev) => {
                    if (prev[index] === h) return prev;
                    const next = prev.slice();
                    next[index] = h;
                    return next;
                  });
                }}
              >
                {cells.slice(1)}
              </View>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

export function MarkdownTableRow({
  nodeKey,
  children,
  isLast = false,
}: {
  nodeKey: string;
  children: ReactNode;
  isLast?: boolean;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View key={nodeKey} style={[s.row, isLast && s.rowLast]}>
      {mapCells(children)}
    </View>
  );
}

function TableCell({
  nodeKey,
  children,
  isLast = false,
}: {
  nodeKey: string;
  children: ReactNode;
  isLast?: boolean;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { columnWidth } = useContext(TableLayoutContext);

  return (
    <View
      key={nodeKey}
      style={[s.cell, !isLast && s.cellBorderRight, { width: columnWidth }]}
    >
      <View style={s.cellInner}>{children}</View>
    </View>
  );
}

export function MarkdownTableHeaderCell(
  props: CellProps & { nodeKey: string; children: ReactNode },
) {
  return <TableCell {...props} />;
}

export function MarkdownTableCell(
  props: CellProps & { nodeKey: string; children: ReactNode },
) {
  return <TableCell {...props} />;
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    scrollWrap: {
      marginTop: 0,
      marginBottom: 10,
      overflow: "hidden",
      alignSelf: "stretch",
      width: "100%",
    },
    scroll: { backgroundColor: "transparent" },
    freezeRow: {
      flexDirection: "row",
      alignSelf: "stretch",
      width: "100%",
    },
    frozenCol: {
      zIndex: 1,
      borderRightWidth: StyleSheet.hairlineWidth,
      borderRightColor: theme.border,
    },
    table: {
      backgroundColor: "transparent",
      alignSelf: "stretch",
    },
    row: {
      flexDirection: "row",
      alignItems: "flex-start",
      backgroundColor: "transparent",
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    rowLast: {
      borderBottomWidth: 0,
    },
    cell: {
      backgroundColor: "transparent",
      minWidth: 0,
    },
    cellBorderRight: {
      borderRightWidth: StyleSheet.hairlineWidth,
      borderRightColor: theme.border,
    },
    cellInner: {
      paddingHorizontal: 12,
      paddingVertical: 10,
      minWidth: 0,
      flexShrink: 1,
    },
  });
}
