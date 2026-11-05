// Russian has more plural forms than English, so counts can't be built by adding an "s".
export type Plural = { one: string; other: string; few?: string; many?: string };
