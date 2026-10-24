// Без похожих символов (0/O, 1/l/I), чтобы пароль можно было продиктовать или переписать
const LOWER = 'abcdefghijkmnpqrstuvwxyz'
const UPPER = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
const DIGITS = '23456789'
const SYMBOLS = '!@#$%^&*-_=+?'
const ALL = LOWER + UPPER + DIGITS + SYMBOLS

function randomIndex(max: number): number {
  // Отсев значений сверх кратного max убирает перекос распределения (modulo bias)
  const limit = Math.floor(0x1_0000_0000 / max) * max
  const buffer = new Uint32Array(1)
  do crypto.getRandomValues(buffer)
  while (buffer[0] >= limit)
  return buffer[0] % max
}

const pick = (alphabet: string) => alphabet[randomIndex(alphabet.length)]

// Криптостойкий пароль: хотя бы по одному символу каждого класса, остальное из общего алфавита
export function generatePassword(length = 16): string {
  const chars = [pick(LOWER), pick(UPPER), pick(DIGITS), pick(SYMBOLS)]
  while (chars.length < length) chars.push(pick(ALL))
  for (let i = chars.length - 1; i > 0; i--) {
    const j = randomIndex(i + 1)
    ;[chars[i], chars[j]] = [chars[j], chars[i]]
  }
  return chars.join('')
}
