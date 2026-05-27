"use client";

export type HeaderCell = {
  text: string;
  row_span?: number;
  col_span?: number;
  kind?: string;
};

export type PivotPreviewProps = {
  columns: string[];
  column_labels?: Record<string, string>;
  rows: Record<string, unknown>[];
  header_rows?: HeaderCell[][];
  row_dims?: string[];
};

export function PivotPreviewTable({
  columns,
  rows,
  header_rows,
  row_dims = [],
}: PivotPreviewProps) {
  const useMultiHeader = header_rows && header_rows.length > 0;

  return (
    <div className="overflow-x-auto border border-gray-200 rounded-lg">
      <table className="w-full text-xs border-collapse min-w-max">
        <thead>
          {useMultiHeader ? (
            header_rows!.map((headerRow, ri) => (
              <tr key={ri} className="border-b border-gray-200 bg-gray-50">
                {headerRow.map((cell, ci) => (
                  <th
                    key={`${ri}-${ci}-${cell.text}`}
                    rowSpan={cell.row_span ?? 1}
                    colSpan={cell.col_span ?? 1}
                    className={`py-2 px-3 text-left font-semibold whitespace-nowrap border-r border-gray-100 last:border-r-0 ${
                      cell.kind === "col_group"
                        ? "text-center text-gray-800 bg-blue-50/80"
                        : cell.kind === "value"
                          ? "text-gray-600 font-medium bg-gray-50"
                          : "text-gray-700 bg-gray-100 sticky left-0 z-10"
                    }`}
                  >
                    {cell.text}
                  </th>
                ))}
              </tr>
            ))
          ) : (
            <tr className="border-b border-gray-200 bg-gray-50">
              {columns.map((k) => (
                <th key={k} className="py-2 px-2 text-left font-medium text-gray-600 whitespace-nowrap">
                  {k}
                </th>
              ))}
            </tr>
          )}
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const isTotal =
              row_dims.length > 0 &&
              String(row[row_dims[0]] ?? "") === "Grand total";
            return (
              <tr
                key={i}
                className={`border-b border-gray-100 ${isTotal ? "bg-gray-100 font-semibold" : "hover:bg-gray-50/80"}`}
              >
                {columns.map((k, colIndex) => (
                  <td
                    key={k}
                    className={`py-2 px-3 whitespace-nowrap border-r border-gray-50 last:border-r-0 ${
                      colIndex < row_dims.length
                        ? "text-gray-900 font-medium bg-white sticky left-0 z-[1] border-r-gray-200"
                        : "text-gray-800 text-right tabular-nums"
                    }`}
                  >
                    {String(row[k] ?? "")}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
