/**
 * A worked layout's own words in each app language. The API writes them in the language of
 * the reply ("Un coche acelera de 0 a 25 m/s en 5 s…" is worked under **Datos**, not
 * **Given**; `modules/chat/worked_language.py`), and the phone lays a worked reply out by its
 * headings in any of them. `docs/fixtures/worked_words.json` holds this table and the
 * API's to one (`workedWords.test.ts`).
 */
export const WORKED_WORDS = {
  en: { given: "Given", required: "Required", solution: "Solution", substitution: "Substitution", steps: "Steps", answer: "Answer", where: "where", solve_for: "Solve for {symbol}" },
  es: { given: "Datos", required: "Incógnita", solution: "Solución", substitution: "Sustitución", steps: "Pasos", answer: "Respuesta", where: "donde", solve_for: "Despejamos {symbol}" },
  fr: { given: "Données", required: "Inconnue", solution: "Solution", substitution: "Application numérique", steps: "Étapes", answer: "Réponse", where: "où", solve_for: "On isole {symbol}" },
  de: { given: "Gegeben", required: "Gesucht", solution: "Lösung", substitution: "Einsetzen", steps: "Schritte", answer: "Antwort", where: "wobei", solve_for: "Umstellen nach {symbol}" },
  it: { given: "Dati", required: "Incognita", solution: "Soluzione", substitution: "Sostituzione", steps: "Passaggi", answer: "Risposta", where: "dove", solve_for: "Ricaviamo {symbol}" },
  pt: { given: "Dados", required: "Incógnita", solution: "Solução", substitution: "Substituição", steps: "Passos", answer: "Resposta", where: "onde", solve_for: "Isolamos {symbol}" },
  ru: { given: "Дано", required: "Найти", solution: "Решение", substitution: "Подстановка", steps: "Шаги", answer: "Ответ", where: "где", solve_for: "Выразим {symbol}" },
  tr: { given: "Verilenler", required: "İstenen", solution: "Çözüm", substitution: "Yerine koyma", steps: "Adımlar", answer: "Yanıt", where: "burada", solve_for: "{symbol} yalnız bırakılır" },
  am: { given: "የተሰጠ", required: "የሚፈለገው", solution: "መፍትሄ", substitution: "እሴቶቹን መተካት", steps: "ደረጃዎች", answer: "መልስ", where: "እዚህ", solve_for: "{symbol}ን ለብቻው ማውጣት" },
} as const;

type HeadingKind = "given" | "required" | "solution" | "substitution" | "steps" | "answer";

/** One heading's word in every language, each once ("Solution" is French too). */
export function workedHeadings(kind: HeadingKind): readonly string[] {
  return [...new Set(Object.values(WORKED_WORDS).map((words) => words[kind]))];
}
