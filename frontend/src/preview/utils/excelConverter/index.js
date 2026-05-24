import { ExcelJSAdapter } from './adapters/index.js';
import { ExcelConverter } from './ExcelConverter.js';

const adapters = new Map();

export const registerAdapter = (name, AdapterClass) => {
  adapters.set(name, AdapterClass);
};

export const getAdapter = (name) => {
  return adapters.get(name);
};

export const hasAdapter = (name) => {
  return adapters.has(name);
};

registerAdapter('exceljs', ExcelJSAdapter);

export const createConverter = (adapterName = 'exceljs', options = {}) => {
  const AdapterClass = getAdapter(adapterName);

  if (!AdapterClass) {
    throw new Error(`Unknown adapter: ${adapterName}. Available adapters: ${Array.from(adapters.keys()).join(', ')}`);
  }

  const adapter = new AdapterClass(options);
  return new ExcelConverter(adapter);
};

export const convertExcelToWorkbook = async (arrayBuffer, adapterName = 'exceljs', options = {}) => {
  const converter = createConverter(adapterName, options);
  return converter.convert(arrayBuffer);
};

export { ExcelConverter } from './ExcelConverter.js';
export * from './adapters/index.js';
export * from './utils/index.js';
