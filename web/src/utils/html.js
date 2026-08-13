export const decodeHtmlEntities = (value) => {
  const text = String(value || '')
  if (typeof window === 'undefined' || !text.includes('&')) return text
  const doc = new DOMParser().parseFromString(text, 'text/html')
  return doc.body.textContent || ''
}
