export interface ProgressIndicator {
  update(current: number, total: number): void;
  reset(): void;
}

export function createProgressIndicator(): ProgressIndicator {
  const barElement = document.getElementById('progress-bar');
  const textElement = document.getElementById('progress-text');

  if (!barElement || !textElement) {
    throw new Error('Progress indicator elements not found in DOM');
  }

  const progressBar = barElement;
  const progressText = textElement;

  function update(current: number, total: number): void {
    const safeTotal = Math.max(1, total);
    const safeCurrent = Math.max(0, Math.min(current, safeTotal));

    const percentage = (safeCurrent / safeTotal) * 100;
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `${safeCurrent} / ${safeTotal}`;
  }

  function reset(): void {
    progressBar.style.width = '0%';
    progressText.textContent = '0 / 0';
  }

  return {
    update,
    reset,
  };
}
