function hslToHex(h: number, s: number, l: number): number {
  s /= 100
  l /= 100

  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs((h / 60) % 2 - 1))
  const m = l - c / 2

  let r = 0, g = 0, b = 0

  if (h >= 0 && h < 60) { r = c; g = x; b = 0 }
  else if (h >= 60 && h < 120) { r = x; g = c; b = 0 }
  else if (h >= 120 && h < 180) { r = 0; g = c; b = x }
  else if (h >= 180 && h < 240) { r = 0; g = x; b = c }
  else if (h >= 240 && h < 300) { r = x; g = 0; b = c }
  else { r = c; g = 0; b = x }

  const toHex = (n: number) => Math.round((n + m) * 255)

  return (toHex(r) << 16) | (toHex(g) << 8) | toHex(b)
}

export function getColorFromId(id: string): number {
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash = id.charCodeAt(i) + ((hash << 5) - hash)
    hash = hash & hash
  }

  const h = Math.abs(hash % 360)
  const s = 60 + (Math.abs(hash >> 8) % 20)
  const l = 45 + (Math.abs(hash >> 16) % 15)

  return hslToHex(h, s, l)
}
