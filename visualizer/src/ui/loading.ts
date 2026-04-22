/**
 * Loading indicator component for displaying asset loading state.
 * Shows "Loading assets..." with a spinner while assets are being preloaded.
 * The indicator blocks UI by signaling that Play should be disabled until loading completes.
 */

export interface LoadingIndicator {
  show(): void;
  hide(): void;
  isVisible(): boolean;
}

export function createLoadingIndicator(): LoadingIndicator {
  const element = document.getElementById('loading-indicator');

  if (!element) {
    throw new Error('Loading indicator element #loading-indicator not found in DOM');
  }

  const loadingElement: HTMLElement = element;

  function show(): void {
    loadingElement.classList.add('visible');
  }

  function hide(): void {
    loadingElement.classList.remove('visible');
  }

  function isVisible(): boolean {
    return loadingElement.classList.contains('visible');
  }

  return {
    show,
    hide,
    isVisible,
  };
}
