"""Historique SQLite : tout ce qui a déjà été récupéré. Jamais publié, jamais purgé automatiquement."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

class Historique:
    """Tous les articles déjà récupérés. Rien n'est effacé automatiquement :
    la page n'affiche que les sources encore listées (voir charger)."""

    def __init__(self, chemin: Path):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(chemin)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id          TEXT PRIMARY KEY,
                source_key  TEXT NOT NULL,
                source      TEXT,
                title       TEXT,
                link        TEXT NOT NULL,
                date        TEXT,
                summary     TEXT,
                image       TEXT,
                kind        TEXT,
                premier_vu  TEXT NOT NULL,
                dernier_vu  TEXT NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source_key)")
        try:
            self.conn.execute("ALTER TABLE articles ADD COLUMN content TEXT")
        except sqlite3.OperationalError:
            pass  # colonne déjà existante

    def enregistrer(self, items: list[dict]) -> int:
        """Ajoute les nouveaux articles, met à jour les anciens. Retourne le nombre d'articles traités."""
        maintenant = datetime.now(timezone.utc).isoformat()
        with self.conn:
            for it in items:
                date = it["date"].isoformat() if it["date"] else None
                self.conn.execute(
                    """
                    INSERT INTO articles (id, source_key, source, title, link, date, summary, content, image, kind, premier_vu, dernier_vu)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        source     = excluded.source,
                        title      = excluded.title,
                        date       = COALESCE(excluded.date, articles.date),
                        summary    = excluded.summary,
                        content    = excluded.content,
                        image      = COALESCE(excluded.image, articles.image),
                        dernier_vu = excluded.dernier_vu
                    """,
                    (f"{it['key']}|{it['link']}", it["key"], it["source"], it["title"], it["link"],
                     date, it["summary"], it.get("content", ""), it["image"], it.get("kind", "rss"), maintenant, maintenant),
                )
        return len(items)

    def charger(self, sources: set[str]) -> list[dict]:
        """Articles des sources données uniquement ; les autres restent en base, hors de la page."""
        if not sources:
            return []
        marques = ",".join("?" * len(sources))
        rows = self.conn.execute(
            f"SELECT source_key, source, title, link, date, summary, content, image, kind "
            f"FROM articles WHERE source_key IN ({marques})",
            tuple(sources),
        ).fetchall()
        return [
            {
                "key": key, "source": source, "title": title, "link": link,
                "date": datetime.fromisoformat(date) if date else None,
                "summary": summary or "", "content": content or "", "image": image, "kind": kind,
            }
            for key, source, title, link, date, summary, content, image, kind in rows
        ]

    def fermer(self) -> None:
        self.conn.close()
