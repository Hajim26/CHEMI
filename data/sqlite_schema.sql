
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS team_members (
  id TEXT PRIMARY KEY, nickname TEXT NOT NULL, university TEXT NOT NULL,
  major TEXT NOT NULL, grade TEXT NOT NULL, campus TEXT NOT NULL,
  email TEXT NOT NULL, bio TEXT NOT NULL, is_synthetic INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS member_skills (
  id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT NOT NULL,
  name TEXT NOT NULL, category TEXT NOT NULL,
  FOREIGN KEY(member_id) REFERENCES team_members(id) ON DELETE CASCADE,
  UNIQUE(member_id,name)
);
CREATE TABLE IF NOT EXISTS member_interests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT NOT NULL,
  category TEXT NOT NULL,
  FOREIGN KEY(member_id) REFERENCES team_members(id) ON DELETE CASCADE,
  UNIQUE(member_id,category)
);
