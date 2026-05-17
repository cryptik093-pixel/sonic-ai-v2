export function midiDataUrl(dataBase64: string): string {
  return `data:audio/midi;base64,${dataBase64}`;
}
