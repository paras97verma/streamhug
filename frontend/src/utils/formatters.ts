export function formatTime(seconds: number | null): string {
  if (seconds === null || isNaN(seconds)) return '00:00';
  
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);

  const mDisplay = m < 10 ? `0${m}` : m;
  const sDisplay = s < 10 ? `0${s}` : s;

  if (h > 0) {
    return `${h}:${mDisplay}:${sDisplay}`;
  }
  return `${mDisplay}:${sDisplay}`;
}
