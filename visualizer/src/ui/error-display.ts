/**
 * Error display component for showing validation and loading errors.
 */

export interface ErrorDisplay {
  showError(message: string): void;
  clearError(): void;
  isVisible(): boolean;
}

export function createErrorDisplay(): ErrorDisplay {
  const element = document.getElementById('error-display');

  if (!element) {
    throw new Error('Error display element #error-display not found in DOM');
  }

  const errorElement: HTMLElement = element;

  function showError(message: string): void {
    errorElement.textContent = message;
    errorElement.classList.add('visible');
  }

  function clearError(): void {
    errorElement.textContent = '';
    errorElement.classList.remove('visible');
  }

  function isVisible(): boolean {
    return errorElement.classList.contains('visible');
  }

  return {
    showError,
    clearError,
    isVisible,
  };
}
