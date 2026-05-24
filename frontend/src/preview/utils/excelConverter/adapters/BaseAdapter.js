export class BaseExcelAdapter {
  constructor(options = {}) {
    this.options = options;
  }

  get name() {
    throw new Error('Adapter must implement name getter');
  }

  async load(arrayBuffer) {
    throw new Error('Adapter must implement load method');
  }

  getSheetNames() {
    throw new Error('Adapter must implement getSheetNames method');
  }

  getSheetData(sheetNameOrIndex) {
    throw new Error('Adapter must implement getSheetData method');
  }

  getSheetCount() {
    throw new Error('Adapter must implement getSheetCount method');
  }

  forEachSheet(callback) {
    throw new Error('Adapter must implement forEachSheet method');
  }

  destroy() {}
}
