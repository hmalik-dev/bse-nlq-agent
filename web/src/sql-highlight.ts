// A hand-rolled tokenizer for the SQL tab. Keywords, strings and comments get a
// color; everything else stays default. Deliberately small: SQLite's SELECT grammar
// is all the guard lets through, so this is the whole vocabulary that matters.

export type TokenKind = "keyword" | "string" | "comment" | "text";

export interface Token {
  kind: TokenKind;
  text: string;
}

const KEYWORDS = new Set(
  (
    "select from where join left inner outer cross on and or not in is null as group by " +
    "order having limit offset distinct case when then else end with union all except " +
    "intersect asc desc between like exists count sum avg min max round coalesce cast " +
    "date strftime substr lower upper length abs total"
  ).split(" "),
);

// One piece at a time: a comment to end of line, a quoted string, a word, or a run of anything else.
const PIECE = /--[^\n]*|'(?:[^']|'')*'?|[A-Za-z_][A-Za-z0-9_]*|[^A-Za-z_'-]+|-/gy;

/** Tokenize one line of SQL. Comments run to the end of the line, so lines tokenize independently. */
export function tokenize(line: string): Token[] {
  const tokens: Token[] = [];
  PIECE.lastIndex = 0;
  for (let match = PIECE.exec(line); match !== null; match = PIECE.exec(line)) {
    tokens.push({ kind: kindOf(match[0]), text: match[0] });
  }
  return tokens;
}

/** Every line of a statement, tokenized, in order; line numbers are the array index plus one. */
export function highlight(sql: string): Token[][] {
  return sql.split("\n").map(tokenize);
}

function kindOf(text: string): TokenKind {
  if (text.startsWith("--")) return "comment";
  if (text.startsWith("'")) return "string";
  if (KEYWORDS.has(text.toLowerCase())) return "keyword";
  return "text";
}
