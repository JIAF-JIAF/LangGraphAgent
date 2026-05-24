export const normalizeCellValue = (value) => {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value;
  }
  if (value instanceof Date) {
    return value.toLocaleString();
  }
  if (value.richText) {
    return value.richText.map((r) => r.text).join('');
  }
  return String(value);
};

export const normalizeRowData = (row, maxCol) => {
  if (!Array.isArray(row)) return new Array(maxCol).fill(null);
  const normalizedRow = [...row];
  while (normalizedRow.length < maxCol) {
    normalizedRow.push(null);
  }
  return normalizedRow;
};
