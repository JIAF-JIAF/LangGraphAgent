import { applyCellStyle, hasCellStyle } from './utils/index.js';

const { createWorkbook } = window.ZONGHENG || {};

export class ExcelConverter {
  constructor(adapter) {
    this.adapter = adapter;
    this.sheetProcessors = [];
  }

  async convert(arrayBuffer) {
    await this.adapter.load(arrayBuffer);

    const zhWorkbook = createWorkbook();

    zhWorkbook.batch(() => {
      this.adapter.forEachSheet((sheetData, sheetName, sheetIndex) => {
        this._processSheet(zhWorkbook, sheetData, sheetName, sheetIndex);
      });
    });

    return zhWorkbook;
  }

  _processSheet(zhWorkbook, sheetData, sheetName, sheetIndex) {
    const { data, styles, merges, rowHeights, colWidths, maxRow, maxCol } = sheetData;

    if (maxRow === 0 || maxCol === 0) return;

    let sheet;
    if (sheetIndex === 0) {
      sheet = zhWorkbook.getActiveSheet();
    } else {
      sheet = zhWorkbook.insertSheet(sheetName);
    }

    this._applyRowHeights(sheet, rowHeights);
    this._applyColWidths(sheet, colWidths);

    const range = sheet.getRange(0, 0, maxRow, maxCol);
    range.setValues(data);

    this._applyCellStyles(sheet, styles);
    this._applyMerges(sheet, merges);

    this.sheetProcessors.forEach((processor) => {
      processor(sheet, sheetData, sheetName, sheetIndex);
    });
  }

  _applyRowHeights(sheet, rowHeights) {
    Object.entries(rowHeights).forEach(([rowIndex, height]) => {
      sheet.setRowHeight(Number(rowIndex), height);
    });
  }

  _applyColWidths(sheet, colWidths) {
    colWidths.forEach((width, colIndex) => {
      if (width) {
        sheet.setColumnWidth(colIndex, width);
      }
    });
  }

  _applyCellStyles(sheet, styles) {
    styles.forEach((styleRow, rowIndex) => {
      if (!styleRow) return;
      styleRow.forEach((cell, colIndex) => {
        if (!hasCellStyle(cell)) return;
        const cellRange = sheet.getRange(rowIndex, colIndex, 1, 1);
        applyCellStyle(cellRange, cell);
      });
    });
  }

  _applyMerges(sheet, merges) {
    merges.forEach((merge) => {
      try {
        const parsed = this._parseMergeRange(merge);
        if (parsed) {
          const { startRow, startCol, endRow, endCol } = parsed;
          const mergeRange = sheet.getRange(
            startRow,
            startCol,
            endRow - startRow + 1,
            endCol - startCol + 1
          );
          mergeRange.merge();
        }
      } catch (e) {
        console.warn('Merge error:', e);
      }
    });
  }

  _parseMergeRange(merge) {
    const match = merge.match(/^([A-Z]+)(\d+):([A-Z]+)(\d+)$/);
    if (!match) return null;

    const startCol = match[1].charCodeAt(0) - 'A'.charCodeAt(0);
    const startRow = parseInt(match[2]) - 1;
    const endCol = match[3].charCodeAt(0) - 'A'.charCodeAt(0);
    const endRow = parseInt(match[4]) - 1;

    return { startRow, startCol, endRow, endCol };
  }

  registerSheetProcessor(processor) {
    this.sheetProcessors.push(processor);
  }

  getAdapter() {
    return this.adapter;
  }

  destroy() {
    this.adapter.destroy();
    this.sheetProcessors = [];
  }
}
