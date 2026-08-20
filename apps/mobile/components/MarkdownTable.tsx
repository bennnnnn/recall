import {
  Children,
  ReactElement,
  ReactNode,
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useMemo,
} from "react";
import {
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";

import { Theme, useTheme } from "@/lib/theme";

type CellProps = { isLast?: boolean };

type RowProps = CellProps & { zebra?: boolean };

type TableLayout = {
  columnWidth: number;
  scrollable: boolean;
};

const TableLayoutContext = createContext<TableLayout>({
  columnWidth: 120,
  scrollable: false,
});

const MIN_COL_WIDTH = 112;
const TABLE_H_PAD = 32;

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
      zebra: index % 2 === 1,
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
  const colCount = Math.max(1, columns);
  const available = Math.max(200, screenWidth - TABLE_H_PAD);
  const fittedWidth = available / colCount;
  const scrollable = fittedWidth < MIN_COL_WIDTH;
  const columnWidth = scrollable ? MIN_COL_WIDTH : fittedWidth;

  const table = (
    <View
      key={nodeKey}
      style={[s.table, scrollable && { width: columnWidth * colCount }]}
    >
      {mapRows(children)}
    </View>
  );

  return (
    <TableLayoutContext.Provider value={{ columnWidth, scrollable }}>
      {scrollable ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator
          style={s.scroll}
          nestedScrollEnabled
        >
          {table}
        </ScrollView>
      ) : (
        <View style={s.wrap}>{table}</View>
      )}
    </TableLayoutContext.Provider>
  );
}

export function MarkdownTableRow({
  nodeKey,
  children,
  isLast = false,
  zebra = false,
}: {
  nodeKey: string;
  children: ReactNode;
  isLast?: boolean;
  zebra?: boolean;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View
      key={nodeKey}
      style={[s.row, zebra && s.rowZebra, isLast && s.rowLast]}
    >
      {mapCells(children)}
    </View>
  );
}

function TableCell({
  nodeKey,
  children,
  isLast = false,
  header = false,
}: {
  nodeKey: string;
  children: ReactNode;
  isLast?: boolean;
  header?: boolean;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { columnWidth, scrollable } = useContext(TableLayoutContext);

  return (
    <View
      key={nodeKey}
      style={[
        s.cell,
        header && s.headerCell,
        !isLast && s.cellBorderRight,
        scrollable ? { width: columnWidth } : s.cellFlex,
      ]}
    >
      <View style={s.cellInner}>{children}</View>
    </View>
  );
}

export function MarkdownTableHeaderCell(
  props: CellProps & { nodeKey: string; children: ReactNode },
) {
  return <TableCell {...props} header />;
}

export function MarkdownTableCell(
  props: CellProps & { nodeKey: string; children: ReactNode },
) {
  return <TableCell {...props} />;
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: { marginVertical: 10, alignSelf: "stretch" },
    scroll: { marginVertical: 10 },
    table: {
      width: "100%",
      borderWidth: 1,
      borderColor: theme.border,
      borderRadius: 12,
      overflow: "hidden",
      backgroundColor: theme.surface,
      alignSelf: "stretch",
    },
    row: {
      flexDirection: "row",
      alignItems: "flex-start",
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    rowZebra: {
      backgroundColor: theme.surfaceAlt,
    },
    rowLast: {
      borderBottomWidth: 0,
    },
    cell: {
      backgroundColor: "transparent",
      minWidth: 0,
    },
    cellFlex: {
      flex: 1,
      flexBasis: 0,
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
    headerCell: {
      backgroundColor: theme.surfaceAlt,
    },
  });
}
