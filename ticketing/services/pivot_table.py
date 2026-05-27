"""
Pivot-table aggregation for the report builder (Excel / Google Sheets style).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from ticketing.services.report_rows import FIELD_LABELS

AggFunc = Literal["count", "sum", "avg", "max", "min"]

DIMENSION_FIELDS = frozenset({
    "complaint_date",
    "grievance_id",
    "high_yn",
    "escalated_yn",
    "overdue_yn",
    "stage",
    "stage_level",
    "complaint_category",
    "resolution_category",
    "status_code",
    "priority",
    "project_name",
    "package_label",
    "location_display",
    "organization_id",
    "is_seah",
    "sla_breached",
    "assigned_officer",
})

MEASURE_FIELDS = frozenset({
    "total_days",
    "days_in_stage",
})

AGGREGATIONS = ("count", "sum", "avg", "max", "min")

AGG_LABELS = {
    "count": "Count",
    "sum": "Sum",
    "avg": "Average",
    "max": "Max",
    "min": "Min",
}


def validate_pivot_config(
    rows: list[str],
    columns: list[str],
    values: list[dict[str, str]],
    filters: dict[str, list[str]],
) -> None:
    for f in rows + columns + list(filters.keys()):
        if f not in DIMENSION_FIELDS:
            raise ValueError(f"Not a dimension field: {f}")
    if not values:
        raise ValueError("At least one value aggregation is required")
    for spec in values:
        field = spec.get("field", "")
        agg = spec.get("agg", "count")
        if agg not in AGGREGATIONS:
            raise ValueError(f"Unknown aggregation: {agg}")
        if agg == "count":
            continue
        if field not in MEASURE_FIELDS:
            raise ValueError(
                f"{agg} requires a numeric measure ({', '.join(sorted(MEASURE_FIELDS))}), got {field!r}"
            )


def _apply_filters(rows: list[dict[str, Any]], filters: dict[str, list[str]]) -> list[dict[str, Any]]:
    if not filters:
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        keep = True
        for field, allowed in filters.items():
            if not allowed:
                continue
            raw = row.get(field)
            val = "(blank)" if raw is None or raw == "" else str(raw)
            if val not in allowed:
                keep = False
                break
        if keep:
            out.append(row)
    return out


def _dim_tuple(row: dict[str, Any], fields: list[str]) -> tuple[str, ...]:
    if not fields:
        return ()
    return tuple(str(row.get(f) or "(blank)") for f in fields)


def _numeric_values(items: list[dict[str, Any]], field: str) -> list[float]:
    nums: list[float] = []
    for it in items:
        v = it.get(field)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            nums.append(float(v))
    return nums


def _aggregate(items: list[dict[str, Any]], field: str, agg: AggFunc) -> int | float | None:
    if agg == "count":
        return len(items)
    nums = _numeric_values(items, field)
    if not nums:
        return None
    if agg == "sum":
        return round(sum(nums), 2)
    if agg == "avg":
        return round(sum(nums) / len(nums), 2)
    if agg == "max":
        return max(nums)
    if agg == "min":
        return min(nums)
    return len(items)


def _value_spec_label(field: str, agg: str) -> str:
    if agg == "count" and field == "ticket_id":
        return "Count"
    measure = FIELD_LABELS.get(field, field)
    return f"{AGG_LABELS.get(agg, agg)} of {measure}"


def _col_group_title(col_dims: list[str], col_key: tuple[str, ...]) -> str:
    """Human-readable column group header, e.g. 'Complaint category: Dust'."""
    if not col_dims:
        return "Values"
    parts: list[str] = []
    for i, dim in enumerate(col_dims):
        dim_label = FIELD_LABELS.get(dim, dim)
        val = col_key[i] if i < len(col_key) else "(blank)"
        if len(col_dims) == 1:
            parts.append(f"{dim_label}: {val}")
        else:
            parts.append(f"{dim_label}={val}")
    return " · ".join(parts) if len(col_dims) > 1 else parts[0]


def _data_column_id(col_index: int, spec_index: int) -> str:
    return f"__pivot_c{col_index}_v{spec_index}"


def build_pivot_table(
    rows: list[dict[str, Any]],
    *,
    row_dims: list[str],
    col_dims: list[str],
    value_specs: list[dict[str, str]],
    filters: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    validate_pivot_config(row_dims, col_dims, value_specs, filters or {})

    filtered = _apply_filters(rows, filters or {})

    row_keys = sorted({_dim_tuple(r, row_dims) for r in filtered})
    if not row_keys:
        row_keys = [()]

    if col_dims:
        col_keys = sorted({_dim_tuple(r, col_dims) for r in filtered})
    else:
        col_keys = [()]

    buckets: dict[tuple[tuple[str, ...], tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for r in filtered:
        rk = _dim_tuple(r, row_dims)
        ck = _dim_tuple(r, col_dims)
        buckets[(rk, ck)].append(r)

    # Stable data column keys + metadata for multi-row headers
    value_columns: list[str] = []
    column_groups: list[dict[str, Any]] = []
    for ci, ck in enumerate(col_keys):
        spec_headers: list[str] = []
        for si, spec in enumerate(value_specs):
            value_columns.append(_data_column_id(ci, si))
            spec_headers.append(_value_spec_label(spec["field"], spec["agg"]))
        column_groups.append({
            "title": _col_group_title(col_dims, ck),
            "col_key": list(ck),
            "value_headers": spec_headers,
            "col_span": len(value_specs),
        })

    output_columns = list(row_dims) + value_columns
    row_dim_labels = [FIELD_LABELS.get(d, d) for d in row_dims]
    col_dim_labels = [FIELD_LABELS.get(d, d) for d in col_dims]

    column_labels: dict[str, str] = {}
    for d in row_dims:
        column_labels[d] = FIELD_LABELS.get(d, d)
    for ci, cg in enumerate(column_groups):
        for si, vh in enumerate(cg["value_headers"]):
            key = value_columns[ci * len(value_specs) + si]
            column_labels[key] = f"{cg['title']} — {vh}"

    flat_rows: list[dict[str, Any]] = []
    for rk in row_keys:
        out: dict[str, Any] = {}
        for i, dim in enumerate(row_dims):
            out[dim] = rk[i] if i < len(rk) else ""
        col_idx = 0
        for ci, ck in enumerate(col_keys):
            items = buckets.get((rk, ck), [])
            for si, spec in enumerate(value_specs):
                field = spec["field"]
                agg = spec["agg"]
                val = _aggregate(items, field, agg)  # type: ignore[arg-type]
                key = value_columns[col_idx]
                out[key] = "" if val is None else val
                col_idx += 1
        flat_rows.append(out)

    if row_dims and flat_rows:
        total: dict[str, Any] = {}
        total[row_dims[0]] = "Grand total"
        for d in row_dims[1:]:
            total[d] = ""
        col_idx = 0
        for ci, ck in enumerate(col_keys):
            all_items: list[dict[str, Any]] = []
            for rk in row_keys:
                all_items.extend(buckets.get((rk, ck), []))
            for si, spec in enumerate(value_specs):
                field = spec["field"]
                agg = spec["agg"]
                val = _aggregate(all_items, field, agg)  # type: ignore[arg-type]
                key = value_columns[col_idx]
                total[key] = "" if val is None else val
                col_idx += 1
        flat_rows.append(total)

    # Header layout for UI / export (Excel-style)
    n_values = len(value_specs)
    header_rows: list[list[dict[str, Any]]] = []

    if col_dims and column_groups:
        row1: list[dict[str, Any]] = []
        for label in row_dim_labels:
            row1.append({
                "text": label,
                "row_span": 2,
                "col_span": 1,
                "kind": "row_dim",
            })

        for cg in column_groups:
            row1.append({
                "text": cg["title"],
                "row_span": 1,
                "col_span": cg["col_span"],
                "kind": "col_group",
            })
        header_rows.append(row1)

        row2: list[dict[str, Any]] = []
        for cg in column_groups:
            for vh in cg["value_headers"]:
                row2.append({
                    "text": vh,
                    "row_span": 1,
                    "col_span": 1,
                    "kind": "value",
                })
        header_rows.append(row2)
    else:
        # No column dimensions — single header row
        row1 = []
        for label in row_dim_labels:
            row1.append({"text": label, "row_span": 1, "col_span": 1, "kind": "row_dim"})
        if not row_dims:
            row1.append({"text": "", "row_span": 1, "col_span": 1, "kind": "corner"})
        for spec in value_specs:
            row1.append({
                "text": _value_spec_label(spec["field"], spec["agg"]),
                "row_span": 1,
                "col_span": 1,
                "kind": "value",
            })
        header_rows.append(row1)

    return {
        "columns": output_columns,
        "column_labels": column_labels,
        "rows": flat_rows[:500],
        "total": len(flat_rows),
        "pivot": True,
        "row_dims": row_dims,
        "col_dims": col_dims,
        "value_specs": value_specs,
        "row_dim_labels": row_dim_labels,
        "col_dim_labels": col_dim_labels,
        "column_groups": column_groups,
        "header_rows": header_rows,
    }
