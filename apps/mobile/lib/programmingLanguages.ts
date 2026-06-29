export const PROGRAMMING_LANGUAGES = [
  { id: "python", label: "Python" },
  { id: "javascript", label: "JavaScript" },
  { id: "typescript", label: "TypeScript" },
  { id: "java", label: "Java" },
  { id: "kotlin", label: "Kotlin" },
  { id: "swift", label: "Swift" },
  { id: "go", label: "Go" },
  { id: "rust", label: "Rust" },
  { id: "cpp", label: "C++" },
  { id: "csharp", label: "C#" },
  { id: "ruby", label: "Ruby" },
  { id: "php", label: "PHP" },
] as const;

export type ProgrammingLanguageId = (typeof PROGRAMMING_LANGUAGES)[number]["id"];

export const DEFAULT_PROGRAMMING_LANGUAGE: ProgrammingLanguageId = "python";

export function programmingLanguageLabel(code: string | null | undefined): string {
  const match = PROGRAMMING_LANGUAGES.find((lang) => lang.id === code);
  return match?.label ?? "Python";
}

export function isProgrammingStack(code: string | null | undefined): boolean {
  if (!code || code === "en") return false;
  return PROGRAMMING_LANGUAGES.some((lang) => lang.id === code);
}
