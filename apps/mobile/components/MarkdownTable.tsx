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

export function tableColumnWidth(viewportWidth: number, columns: number): number {
  const colCount = Math.max(1, columns);
  const available = Math.max(200, viewportWidth);
  return Math.max(MIN_COL_WIDTH, available / colCount);
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

  return (
    <TableLayoutContext.Provider value={{ columnWidth }}>
      <View
        style={s.scrollWrap}
        onLayout={(e) => {
          const w = Math.round(e.nativeEvent.layout.width);
          if (w > 0 && Math.abs(w - viewportW) > 1) setViewportW(w);
        }}
      >
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
      </View>
    </TableLayoutContext.Provider>
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
      marginVertical: 10,
      overflow: "hidden",
      alignSelf: "stretch",
      width: "100%",
    },
    scroll: { backgroundColor: "transparent" },
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
