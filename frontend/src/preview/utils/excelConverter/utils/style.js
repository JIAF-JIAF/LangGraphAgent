import { argbToHex } from './color.js';

const HORIZONTAL_ALIGN_MAP = {
  left: 'left',
  center: 'center',
  right: 'right',
};

const VERTICAL_ALIGN_MAP = {
  top: 'top',
  middle: 'middle',
  bottom: 'bottom',
};

export const applyFontStyle = (range, font) => {
  if (!font) return;

  if (font.size) {
    range.setFontSize(font.size);
  }
  if (font.bold) {
    range.setFontWeight('bold');
  }
  if (font.italic) {
    range.setFontStyle('italic');
  }
  if (font.underline) {
    range.setTextUnderline('single');
  }
  if (font.color?.argb) {
    const hexColor = argbToHex(font.color.argb);
    if (hexColor) {
      range.setFontColor(hexColor);
    }
  }
};

export const applyFillStyle = (range, fill) => {
  if (!fill || fill.type !== 'pattern' || !fill.fgColor) return;

  const hexColor = argbToHex(fill.fgColor.argb);
  if (hexColor) {
    range.setBackgroundColor(hexColor);
  }
};

export const applyAlignmentStyle = (range, alignment) => {
  if (!alignment) return;

  if (alignment.horizontal && HORIZONTAL_ALIGN_MAP[alignment.horizontal]) {
    range.setHorizontalAlignment(HORIZONTAL_ALIGN_MAP[alignment.horizontal]);
  }
  if (alignment.vertical && VERTICAL_ALIGN_MAP[alignment.vertical]) {
    range.setVerticalAlignment(VERTICAL_ALIGN_MAP[alignment.vertical]);
  }
  if (alignment.wrapText) {
    range.setWordWrap('autoWrap');
  }
};

export const applyBorderStyle = (range, border) => {
  if (!border) return;
};

export const applyCellStyle = (range, cell) => {
  if (!cell?.style) return;

  const { font, fill, alignment, border } = cell.style;

  applyFontStyle(range, font);
  applyFillStyle(range, fill);
  applyAlignmentStyle(range, alignment);
  applyBorderStyle(range, border);
};

export const hasCellStyle = (cell) => {
  if (!cell?.style) return false;
  const { font, fill, alignment } = cell.style;
  return !!(font || fill || alignment);
};
