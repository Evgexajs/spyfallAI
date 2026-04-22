export type FileSelectedCallback = (content: string, fileName: string) => void;

export interface FileSelector {
  onFileSelected(callback: FileSelectedCallback): void;
  getSelectedFileName(): string | null;
  reset(): void;
}

export function createFileSelector(): FileSelector {
  const fileButton = document.getElementById('file-button') as HTMLButtonElement | null;
  const fileInput = document.getElementById('file-input') as HTMLInputElement | null;
  const fileNameSpan = document.getElementById('file-name') as HTMLSpanElement | null;

  if (!fileButton || !fileInput || !fileNameSpan) {
    throw new Error('File selector elements not found in DOM');
  }

  let selectedFileName: string | null = null;
  let callback: FileSelectedCallback | null = null;

  fileButton.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file) {
      return;
    }

    if (!file.name.endsWith('.json')) {
      fileNameSpan.textContent = 'Ошибка: только .json файлы';
      selectedFileName = null;
      return;
    }

    selectedFileName = file.name;
    fileNameSpan.textContent = file.name;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result;
      if (typeof content === 'string' && callback) {
        callback(content, file.name);
      }
    };
    reader.onerror = () => {
      fileNameSpan.textContent = 'Ошибка чтения файла';
      selectedFileName = null;
    };
    reader.readAsText(file);
  });

  return {
    onFileSelected(cb: FileSelectedCallback): void {
      callback = cb;
    },

    getSelectedFileName(): string | null {
      return selectedFileName;
    },

    reset(): void {
      selectedFileName = null;
      fileNameSpan.textContent = 'Файл не выбран';
      fileInput.value = '';
    }
  };
}
