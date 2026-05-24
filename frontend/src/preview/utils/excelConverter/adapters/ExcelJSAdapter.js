import ExcelJS from 'exceljs';
import { BaseExcelAdapter } from './BaseAdapter.js';
import { normalizeCellValue, normalizeRowData, applyCellStyle, hasCellStyle } from '../utils/index.js';

export class ExcelJSAdapter extends BaseExcelAdapter {
  constructor(options = {}) {
    super(options);
    this.workbook = null;
  }

  get name() {
    return 'exceljs';
  }

  async load(arrayBuffer) {
    this.workbook = new ExcelJS.Workbook();
    await this.workbook.xlsx.load(arrayBuffer);
    return this.workbook;
  }

  getSheetNames() {
    if (!this.workbook) return [];
    return this.workbook.worksheets.map((ws) => ws.name);
  }

  getSheetCount() {
    if (!this.workbook) return 0;
    return this.workbook.worksheets.length;
  }

  getSheetData(sheetNameOrIndex) {
    const worksheet = this._getWorksheet(sheetNameOrIndex);
    if (!worksheet) return null;

    return this._extractSheetData(worksheet);
  }

  forEachSheet(callback) {
    if (!this.workbook) return;
    this.workbook.worksheets.forEach((worksheet, index) => {
      const sheetData = this._extractSheetData(worksheet);
      callback(sheetData, worksheet.name, index);
    });
  }

  _getWorksheet(sheetNameOrIndex) {
    if (!this.workbook) return null;

    if (typeof sheetNameOrIndex === 'number') {
      return this.workbook.worksheets[sheetNameOrIndex];
    }

    return this.workbook.getWorksheet(sheetNameOrIndex);
  }

  _extractSheetData(worksheet) {
    const rowCount = worksheet.rowCount;
    const columnCount = worksheet.columnCount;

    if (rowCount === 0 || columnCount === 0) {
      return { data: [], styles: [], merges: [], rowHeights: {}, colWidths: [] };
    }

    const data = [];
    const styles = [];
    const merges = [];
    const rowHeights = {};
    const colWidths = [];

    worksheet.eachRow((row, rowNumber) => {
      const rowData = [];
      const styleRow = [];
      row.eachCell({ includeEmpty: true }, (cell, colNumber) => {
        rowData.push(normalizeCellValue(cell.value));
        styleRow.push(cell);
      });
      data[rowNumber - 1] = rowData;
      styles[rowNumber - 1] = styleRow;
    });

    const maxRow = data.length;
    const maxCol = Math.max(...data.map((r) => r?.length || 0), columnCount);

    if (maxRow === 0 || maxCol === 0) {
      return { data: [], styles: [], merges: [], rowHeights: {}, colWidths: [] };
    }

    const normalizedData = data.map((row) => normalizeRowData(row, maxCol));

    worksheet.eachRow((row, rowNumber) => {
      const excelRow = worksheet.getRow(rowNumber);
      if (excelRow.height) {
        rowHeights[rowNumber - 1] = excelRow.height;
      }
    });

    for (let colNumber = 1; colNumber <= columnCount; colNumber++) {
      const excelCol = worksheet.getColumn(colNumber);
      if (excelCol.width) {
        colWidths[colNumber - 1] = excelCol.width * 8;
      }
    }

    worksheet.model.merges?.forEach((merge) => {
      merges.push(merge);
    });

    return {
      data: normalizedData,
      styles,
      merges,
      rowHeights,
      colWidths,
      maxRow,
      maxCol,
    };
  }

  destroy() {
    this.workbook = null;
  }
}
